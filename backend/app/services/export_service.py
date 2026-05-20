"""Export service — Unity-ready package generation from asset versions."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import zipfile
from io import BytesIO
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.storage import StorageClient, get_storage
from app.models import Asset, AssetVersion

logger = logging.getLogger(__name__)

_README_TEMPLATE = """\
{asset_name} — Unity Import Instructions
========================================

Version: {version}
Exported from ArtPlatform

Folder structure:
  Models/      → FBX or GLB mesh file
  Textures/    → Albedo, Normal, Metallic-Roughness maps (if available)

Unity import steps:
1. Drag this folder into your Unity project's Assets/ directory.
2. Select the model file in the Project window.
3. In the Inspector, configure:
   - Scale Factor: 1.0
   - Import Animations: enabled (if present)
   - Material Creation Mode: Import via MaterialDescription
4. Apply the textures:
   - Assign Albedo to the material's Albedo map.
   - Assign Normal to the Normal Map slot.
   - Assign MR to the Metallic / Smoothness maps.
5. Adjust texture import settings:
   - Normal map: check "Create from Grayscale" if needed.
   - Set Texture Type to "Normal Map" for the normal texture.
"""


class ExportService:
    def __init__(self, storage: StorageClient | None = None) -> None:
        self.storage = storage or get_storage()

    async def _fetch_asset_and_version(
        self, asset_id: UUID, version: int, db: AsyncSession
    ) -> tuple[Asset, AssetVersion]:
        stmt = (
            select(Asset)
            .where(Asset.id == asset_id)
            .options(selectinload(Asset.versions))
        )
        result = await db.execute(stmt)
        asset = result.scalar_one_or_none()
        if asset is None:
            raise ValueError(f"Asset {asset_id} not found")

        ver_stmt = select(AssetVersion).where(
            AssetVersion.asset_id == asset_id,
            AssetVersion.version == version,
        )
        ver_result = await db.execute(ver_stmt)
        version_obj = ver_result.scalar_one_or_none()
        if version_obj is None:
            raise ValueError(f"Version {version} not found for asset {asset_id}")

        return asset, version_obj

    def _collect_version_files(self, asset: Asset, target_version: AssetVersion) -> list[tuple[str, str]]:
        """Gather (storage_key, relative_zip_path) pairs for all versions up to target.

        Model file comes from the target version. Textures are gathered from the
        most recent version that has each texture key (heuristic: any non-model file).
        """
        files: list[tuple[str, str]] = []
        safe_name = asset.name.replace(" ", "_")
        model_ext = target_version.file_format

        files.append((target_version.storage_key, f"{safe_name}/Models/{safe_name}.{model_ext}"))

        texture_types = {
            "albedo": f"{safe_name}/Textures/{safe_name}_Albedo.png",
            "normal": f"{safe_name}/Textures/{safe_name}_Normal.png",
            "mr": f"{safe_name}/Textures/{safe_name}_MR.png",
        }

        for ver in reversed(asset.versions):
            if ver.version > target_version.version:
                continue
            key_lower = ver.storage_key.lower()
            for label, zip_path in texture_types.items():
                already = any(zp == zip_path for _, zp in files)
                if not already and label in key_lower:
                    ext = ver.file_format
                    files.append((ver.storage_key, f"{safe_name}/Textures/{safe_name}_{label.capitalize()}.{ext}"))

        return files

    async def export_as_unity_package(self, asset_id: UUID, version: int, db: AsyncSession) -> str:
        asset, target_version = await self._fetch_asset_and_version(asset_id, version, db)

        safe_name = asset.name.replace(" ", "_")
        file_pairs = self._collect_version_files(asset, target_version)

        readme_text = _README_TEMPLATE.format(asset_name=asset.name, version=version)

        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for storage_key, zip_path in file_pairs:
                try:
                    data = self.storage.download_file(storage_key)
                    zf.writestr(zip_path, data)
                except Exception:
                    pass

            zf.writestr(f"{safe_name}/README.txt", readme_text)

        zip_bytes = buf.getvalue()
        zip_key = f"exports/{asset_id}/v{version}/{safe_name}_Unity.zip"
        self.storage.upload_file(zip_key, zip_bytes, "application/zip")

        return self.storage.generate_presigned_url(zip_key)

    async def export_as_glb(self, asset_id: UUID, version: int, db: AsyncSession) -> str:
        _, target_version = await self._fetch_asset_and_version(asset_id, version, db)
        return self.storage.generate_presigned_url(target_version.storage_key)

    async def export_as_fbx(self, asset_id: UUID, version: int, db: AsyncSession) -> str:
        asset, target_version = await self._fetch_asset_and_version(asset_id, version, db)

        glb_data = self.storage.download_file(target_version.storage_key)

        safe_name = asset.name.replace(" ", "_")
        fbx_key = f"exports/{asset_id}/v{version}/{safe_name}.fbx"

        blender_bin = shutil.which("blender")
        if blender_bin:
            fbx_data = self._convert_glb_to_fbx_blender(glb_data, blender_bin)
        else:
            fbx_data = self._convert_glb_to_fbx_trimesh(glb_data)
            if fbx_data is None:
                fbx_data = glb_data
                fbx_key = f"exports/{asset_id}/v{version}/{safe_name}.glb"

        self.storage.upload_file(fbx_key, fbx_data, "model/fbx")
        return self.storage.generate_presigned_url(fbx_key)

    def _convert_glb_to_fbx_blender(self, glb_data: bytes, blender_bin: str) -> bytes:
        with tempfile.TemporaryDirectory() as tmpdir:
            glb_path = os.path.join(tmpdir, "input.glb")
            fbx_path = os.path.join(tmpdir, "output.fbx")
            script_path = os.path.join(tmpdir, "convert.py")

            with open(glb_path, "wb") as f:
                f.write(glb_data)

            script = (
                "import bpy, sys\n"
                "bpy.ops.wm.read_factory_settings(use_empty=True)\n"
                f"bpy.ops.import_scene.gltf(filepath=r'{glb_path}')\n"
                "for obj in list(bpy.data.objects):\n"
                "    if obj.type in ('MESH', 'ARMATURE'):\n"
                "        obj.select_set(True)\n"
                "        bpy.context.view_layer.objects.active = obj\n"
                "    else:\n"
                "        bpy.data.objects.remove(obj, do_unlink=True)\n"
                "try:\n"
                f"    bpy.ops.export_scene.fbx(filepath=r'{fbx_path}', use_selection=True)\n"
                "except Exception as e:\n"
                "    print(f'FBX export error: {e}', file=sys.stderr)\n"
                "    sys.exit(1)\n"
            )
            with open(script_path, "w") as f:
                f.write(script)

            result = subprocess.run(
                [blender_bin, "--background", "--python", script_path],
                capture_output=True, text=True, timeout=120,
            )

            if result.returncode != 0:
                logger.warning("Blender FBX export failed (exit %d): %s", result.returncode, result.stderr[-500:])
                raise RuntimeError(f"Blender FBX export failed: {result.stderr[-500:]}")

            if not os.path.isfile(fbx_path):
                raise RuntimeError("Blender FBX export produced no output file")

            with open(fbx_path, "rb") as f:
                return f.read()

    def _convert_glb_to_fbx_trimesh(self, glb_data: bytes) -> bytes | None:
        try:
            import trimesh
            mesh = trimesh.load(BytesIO(glb_data), file_type="glb")
            fbx_buf = BytesIO()
            mesh.export(fbx_buf, file_type="fbx")
            return fbx_buf.getvalue()
        except Exception:
            return None

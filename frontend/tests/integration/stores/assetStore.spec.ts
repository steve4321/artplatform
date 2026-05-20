import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useAssetStore } from '../../../src/stores/assetStore';

describe('assetStore', () => {
  beforeEach(() => {
    useAssetStore.setState({
      assets: [],
      isLoading: false,
      error: null,
      filters: { search: '', assetType: 'all', state: 'all' },
      page: 1,
      pageSize: 20,
      total: 0,
    });
  });

  describe('setFilters', () => {
    it('设置搜索筛选条件', () => {
      const { setFilters } = useAssetStore.getState();
      setFilters({ search: 'test' });
      const state = useAssetStore.getState();
      expect(state.filters.search).toBe('test');
    });

    it('设置资产类型筛选', () => {
      const { setFilters } = useAssetStore.getState();
      setFilters({ assetType: 'model_3d' });
      const state = useAssetStore.getState();
      expect(state.filters.assetType).toBe('model_3d');
    });

    it('设置状态筛选', () => {
      const { setFilters } = useAssetStore.getState();
      setFilters({ state: 'review' });
      const state = useAssetStore.getState();
      expect(state.filters.state).toBe('review');
    });

    it('多个筛选条件一起设置', () => {
      const { setFilters } = useAssetStore.getState();
      setFilters({ search: 'sword', assetType: 'model_3d', state: 'approved' });
      const state = useAssetStore.getState();
      expect(state.filters.search).toBe('sword');
      expect(state.filters.assetType).toBe('model_3d');
      expect(state.filters.state).toBe('approved');
    });

    it('设置筛选条件后重置页码为1', () => {
      useAssetStore.setState({ page: 5 });
      const { setFilters } = useAssetStore.getState();
      setFilters({ search: 'test' });
      const state = useAssetStore.getState();
      expect(state.page).toBe(1);
    });
  });

  describe('setPage', () => {
    it('设置页码', () => {
      const { setPage } = useAssetStore.getState();
      setPage(3);
      const state = useAssetStore.getState();
      expect(state.page).toBe(3);
    });
  });

  describe('resetFilters', () => {
    it('重置所有筛选条件', () => {
      useAssetStore.setState({
        filters: { search: 'test', assetType: 'model_3d', state: 'review' },
        page: 5,
      });

      const { resetFilters } = useAssetStore.getState();
      resetFilters();

      const state = useAssetStore.getState();
      expect(state.filters.search).toBe('');
      expect(state.filters.assetType).toBe('all');
      expect(state.filters.state).toBe('all');
      expect(state.page).toBe(1);
    });
  });

  describe('getAssetById', () => {
    it('返回匹配的资产', () => {
      const mockAsset = { id: 'asset-1', name: 'Test Asset', assetType: 'model_3d' as const, state: 'draft' as const };
      useAssetStore.setState({ assets: [mockAsset] });

      const { getAssetById } = useAssetStore.getState();
      const result = getAssetById('asset-1');

      expect(result).toEqual(mockAsset);
    });

    it('未找到返回 undefined', () => {
      useAssetStore.setState({ assets: [] });
      const { getAssetById } = useAssetStore.getState();
      const result = getAssetById('nonexistent');
      expect(result).toBeUndefined();
    });
  });

  describe('getDownloadUrl', () => {
    it('生成正确的下载 URL', () => {
      const { getDownloadUrl } = useAssetStore.getState();
      const url = getDownloadUrl('asset-123', 2);
      expect(url).toBe('/api/v1/assets/asset-123/versions/2/download');
    });

    it('不同版本号生成不同 URL', () => {
      const { getDownloadUrl } = useAssetStore.getState();
      const url1 = getDownloadUrl('asset-1', 1);
      const url2 = getDownloadUrl('asset-1', 3);
      expect(url1).not.toBe(url2);
    });
  });

  describe('状态初始化', () => {
    it('初始状态为空列表', () => {
      const state = useAssetStore.getState();
      expect(state.assets).toEqual([]);
      expect(state.total).toBe(0);
    });

    it('初始无加载状态', () => {
      const state = useAssetStore.getState();
      expect(state.isLoading).toBe(false);
    });

    it('初始无错误', () => {
      const state = useAssetStore.getState();
      expect(state.error).toBe(null);
    });

    it('默认分页20条', () => {
      const state = useAssetStore.getState();
      expect(state.pageSize).toBe(20);
    });
  });
});

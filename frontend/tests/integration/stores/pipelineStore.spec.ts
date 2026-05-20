import { describe, it, expect, beforeEach } from 'vitest';
import { usePipelineStore } from '../../../src/stores/pipelineStore';

describe('pipelineStore', () => {
  beforeEach(() => {
    usePipelineStore.setState({
      currentRun: null,
      steps: [],
      isLoading: false,
      error: null,
      selectedStageIndex: null,
      _pollIntervalId: null,
      _pollCount: 0,
    });
  });

  afterEach(() => {
    const state = usePipelineStore.getState();
    if (state._pollIntervalId) {
      clearInterval(state._pollIntervalId);
    }
  });

  describe('resetPipeline', () => {
    it('重置所有状态', () => {
      usePipelineStore.setState({
        currentRun: { id: 'pipeline-1' } as any,
        steps: [{ id: 'step-1' }] as any,
        error: 'some error',
        selectedStageIndex: 2,
      });

      const { resetPipeline } = usePipelineStore.getState();
      resetPipeline();

      const state = usePipelineStore.getState();
      expect(state.currentRun).toBeNull();
      expect(state.steps).toEqual([]);
      expect(state.error).toBeNull();
      expect(state.selectedStageIndex).toBeNull();
    });
  });

  describe('selectStage', () => {
    it('设置选中的阶段索引', () => {
      const { selectStage } = usePipelineStore.getState();
      selectStage(2);
      const state = usePipelineStore.getState();
      expect(state.selectedStageIndex).toBe(2);
    });

    it('可设置为 null', () => {
      usePipelineStore.setState({ selectedStageIndex: 2 });
      const { selectStage } = usePipelineStore.getState();
      selectStage(null);
      const state = usePipelineStore.getState();
      expect(state.selectedStageIndex).toBeNull();
    });

    it('可以切换选中阶段', () => {
      const { selectStage } = usePipelineStore.getState();
      selectStage(0);
      expect(usePipelineStore.getState().selectedStageIndex).toBe(0);
      selectStage(2);
      expect(usePipelineStore.getState().selectedStageIndex).toBe(2);
    });
  });

  describe('getCurrentModelUrl', () => {
    it('completed 状态且有 GLB 返回 URL', () => {
      usePipelineStore.setState({
        currentRun: { id: 'pipeline-1', status: 'completed' } as any,
        steps: [
          {
            status: 'completed',
            outputArtifactIds: ['models/test.glb'],
          },
        ],
        selectedStageIndex: null,
      });

      const { getCurrentModelUrl } = usePipelineStore.getState();
      const url = getCurrentModelUrl();

      expect(url).toBe('/local-storage/models/test.glb');
    });

    it('completed 状态选择特定阶段返回该阶段 GLB', () => {
      usePipelineStore.setState({
        currentRun: { id: 'pipeline-1', status: 'completed' } as any,
        steps: [
          { status: 'completed', outputArtifactIds: ['stage1.glb'] },
          { status: 'completed', outputArtifactIds: ['stage2.glb'] },
        ],
        selectedStageIndex: 1,
      });

      const { getCurrentModelUrl } = usePipelineStore.getState();
      const url = getCurrentModelUrl();

      expect(url).toBe('/local-storage/stage2.glb');
    });

    it('非 completed 状态返回 null', () => {
      usePipelineStore.setState({
        currentRun: { id: 'pipeline-1', status: 'running' } as any,
        steps: [],
        selectedStageIndex: null,
      });

      const { getCurrentModelUrl } = usePipelineStore.getState();
      const url = getCurrentModelUrl();

      expect(url).toBeNull();
    });

    it('无 currentRun 返回 null', () => {
      const { getCurrentModelUrl } = usePipelineStore.getState();
      const url = getCurrentModelUrl();
      expect(url).toBeNull();
    });

    it('无 GLB 文件返回 null', () => {
      usePipelineStore.setState({
        currentRun: { id: 'pipeline-1', status: 'completed' } as any,
        steps: [
          {
            status: 'completed',
            outputArtifactIds: ['image.png'],
          },
        ],
        selectedStageIndex: null,
      });

      const { getCurrentModelUrl } = usePipelineStore.getState();
      const url = getCurrentModelUrl();

      expect(url).toBeNull();
    });
  });

  describe('getCurrentImageUrls', () => {
    it('completed 状态返回图片 URL 列表', () => {
      usePipelineStore.setState({
        currentRun: { id: 'pipeline-1', status: 'completed' } as any,
        steps: [
          {
            status: 'completed',
            outputArtifactIds: ['img1.png', 'img2.jpg'],
          },
        ],
        selectedStageIndex: null,
      });

      const { getCurrentImageUrls } = usePipelineStore.getState();
      const urls = getCurrentImageUrls();

      expect(urls).toEqual(['/local-storage/img1.png', '/local-storage/img2.jpg']);
    });

    it('非 completed 状态返回空数组', () => {
      usePipelineStore.setState({
        currentRun: { id: 'pipeline-1', status: 'running' } as any,
        steps: [],
        selectedStageIndex: null,
      });

      const { getCurrentImageUrls } = usePipelineStore.getState();
      const urls = getCurrentImageUrls();

      expect(urls).toEqual([]);
    });

    it('无 currentRun 返回空数组', () => {
      const { getCurrentImageUrls } = usePipelineStore.getState();
      const urls = getCurrentImageUrls();
      expect(urls).toEqual([]);
    });

    it('过滤非图片文件', () => {
      usePipelineStore.setState({
        currentRun: { id: 'pipeline-1', status: 'completed' } as any,
        steps: [
          {
            status: 'completed',
            outputArtifactIds: ['img.png', 'model.glb', 'other.jpg'],
          },
        ],
        selectedStageIndex: null,
      });

      const { getCurrentImageUrls } = usePipelineStore.getState();
      const urls = getCurrentImageUrls();

      expect(urls).toHaveLength(2);
      expect(urls).toContain('/local-storage/img.png');
      expect(urls).toContain('/local-storage/other.jpg');
      expect(urls).not.toContain('/local-storage/model.glb');
    });
  });

  describe('状态初始化', () => {
    it('初始无当前管线', () => {
      const state = usePipelineStore.getState();
      expect(state.currentRun).toBeNull();
    });

    it('初始无阶段数据', () => {
      const state = usePipelineStore.getState();
      expect(state.steps).toEqual([]);
    });

    it('初始无加载状态', () => {
      const state = usePipelineStore.getState();
      expect(state.isLoading).toBe(false);
    });

    it('初始无错误', () => {
      const state = usePipelineStore.getState();
      expect(state.error).toBeNull();
    });

    it('初始无选中阶段', () => {
      const state = usePipelineStore.getState();
      expect(state.selectedStageIndex).toBeNull();
    });
  });
});

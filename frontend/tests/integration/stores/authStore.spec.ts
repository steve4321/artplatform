import { describe, it, expect, beforeEach } from 'vitest';
import { useAuthStore } from '../../../src/stores/authStore';

describe('authStore', () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: null,
      token: null,
      isLoading: false,
      isAuthenticated: false,
      error: null,
    });
    localStorage.removeItem('auth_token');
  });

  describe('logout', () => {
    it('登出清除用户信息', () => {
      useAuthStore.setState({
        user: { id: '1', email: 'test@test.com', displayName: 'Test', role: 'admin' },
        token: 'some-token',
        isAuthenticated: true,
      });

      const { logout } = useAuthStore.getState();
      logout();

      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.token).toBeNull();
      expect(state.isAuthenticated).toBe(false);
    });

    it('登出清除 localStorage token', () => {
      localStorage.setItem('auth_token', 'test-token');
      useAuthStore.setState({ token: 'test-token' });

      const { logout } = useAuthStore.getState();
      logout();

      expect(localStorage.getItem('auth_token')).toBeFalsy();
    });
  });

  describe('initial state', () => {
    it('初始未认证', () => {
      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(false);
    });

    it('初始无用户', () => {
      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
    });

    it('初始无 token', () => {
      const state = useAuthStore.getState();
      expect(state.token).toBeNull();
    });

    it('初始无加载状态', () => {
      const state = useAuthStore.getState();
      expect(state.isLoading).toBe(false);
    });
  });

  describe('setState', () => {
    it('可以设置用户信息', () => {
      const mockUser = { id: '1', email: 'test@test.com', displayName: 'Test', role: 'admin' };
      useAuthStore.setState({ user: mockUser });

      const state = useAuthStore.getState();
      expect(state.user?.email).toBe('test@test.com');
    });

    it('可以设置认证状态', () => {
      useAuthStore.setState({ isAuthenticated: true, token: 'valid-token' });

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(true);
      expect(state.token).toBe('valid-token');
    });

    it('可以设置加载状态', () => {
      useAuthStore.setState({ isLoading: true });

      const state = useAuthStore.getState();
      expect(state.isLoading).toBe(true);
    });

    it('可以设置错误信息', () => {
      useAuthStore.setState({ error: 'Login failed' });

      const state = useAuthStore.getState();
      expect(state.error).toBe('Login failed');
    });
  });
});

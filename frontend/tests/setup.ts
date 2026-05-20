import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Mock localStorage
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
};
vi.stubGlobal('localStorage', localStorageMock);

// Mock window.location
Object.defineProperty(window, 'location', {
  value: { href: '', pathname: '/', search: '', hash: '' },
  writable: true,
});

// Mock window.confirm
vi.stubGlobal('confirm', vi.fn(() => true));
vi.stubGlobal('alert', vi.fn());

// Mock fetch
global.fetch = vi.fn();

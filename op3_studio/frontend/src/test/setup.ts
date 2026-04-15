import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

// Stub Three.js's WebGLRenderer at the module level so SceneManager
// can mount in jsdom without a real GL context.
vi.mock("three", async (orig) => {
  const real = await orig<typeof import("three")>();
  class FakeRenderer {
    domElement = document.createElement("canvas");
    setSize() {}
    setPixelRatio() {}
    render() {}
    dispose() {}
    shadowMap = { enabled: false, type: 0 };
    toneMapping = 0;
    toneMappingExposure = 1;
  }
  return { ...real, WebGLRenderer: FakeRenderer };
});

vi.mock("three/examples/jsm/controls/OrbitControls.js", () => ({
  OrbitControls: class {
    enableDamping = false;
    dampingFactor = 0;
    target = { set() {} };
    update() {}
    dispose() {}
  },
}));

declare module '@metamask/logo' {
  type Options = {
    pxNotRatio?: boolean;
    width?: number;
    height?: number;
    followMouse?: boolean;
    slowDrift?: boolean;
  };
  type Viewer = {
    container: HTMLElement;
    lookAt: (pos: { x: number; y: number }) => void;
    setFollowMouse: (v: boolean) => void;
    stopAnimation: () => void;
  };
  const ModelViewer: (opts?: Options) => Viewer;
  export = ModelViewer;
}


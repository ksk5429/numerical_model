import React from "react";

interface State { hasError: boolean; error: Error | null; }

export class ErrorBoundary extends React.Component<
  { children: React.ReactNode }, State
> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error("[op3-studio] uncaught error:", error, info);
  }

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <div className="p-6 bg-op3-bg text-gray-100 h-screen
                      flex flex-col items-center justify-center gap-3">
        <div className="text-op3-danger text-lg font-semibold">
          Op3 Studio crashed
        </div>
        <pre className="bg-black/40 p-3 rounded text-xs text-gray-300
                        max-w-lg overflow-auto">
          {this.state.error?.stack || this.state.error?.message
            || "unknown error"}
        </pre>
        <button
          onClick={() => this.setState({ hasError: false, error: null })}
          className="px-3 py-1 bg-op3-accent/20 border border-op3-accent/40
                     rounded text-op3-accent text-sm"
        >Reset</button>
      </div>
    );
  }
}

export default ErrorBoundary;

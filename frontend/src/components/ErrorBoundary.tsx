import { Component, type ReactNode } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";

interface Props {
  children: ReactNode;
}
interface State {
  error: Error | null;
}

/** Prevents a map/component crash from whitescreening the whole app. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: unknown) {
    console.error("UI crashed:", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex-1 flex items-center justify-center bg-slate-950 p-6">
          <div className="max-w-md text-center">
            <div className="w-14 h-14 bg-red-500/15 border border-red-500/30 rounded-xl flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="w-7 h-7 text-red-400" />
            </div>
            <h2 className="text-lg font-bold text-white mb-2">
              Something went wrong
            </h2>
            <p className="text-sm text-slate-400 mb-4 break-words">
              {this.state.error.message}
            </p>
            <button
              onClick={() => this.setState({ error: null })}
              className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-4 py-2 rounded-lg"
            >
              <RotateCcw className="w-4 h-4" />
              Try again
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

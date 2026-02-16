import { Routes, Route, Link } from "react-router-dom";
import Overview from "./pages/overview";
import FlagPage from "./pages/flag";

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-border bg-card">
        <div className="mx-auto max-w-6xl px-6 py-4 flex items-center gap-3">
          <Link to="/" className="flex items-center gap-2 font-semibold text-lg tracking-tight">
            <span className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground text-xs font-bold">
              m
            </span>
            modelab
          </Link>
          <span className="text-muted-foreground text-sm ml-auto">A/B Testing for LLMs</span>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/flags/:name" element={<FlagPage />} />
        </Routes>
      </main>
    </div>
  );
}

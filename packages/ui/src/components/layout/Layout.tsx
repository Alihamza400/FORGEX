import { Toaster } from "react-hot-toast";
import { Sidebar } from "./Sidebar";
import type { ReactNode } from "react";

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <div className="p-6 lg:p-8 max-w-7xl mx-auto animate-fade-in">
          {children}
        </div>
      </main>
      <Toaster
        position="bottom-right"
        toastOptions={{
          duration: 4000,
        }}
      />
    </div>
  );
}

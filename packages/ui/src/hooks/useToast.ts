import toast from "react-hot-toast";

export function useToast() {
  return {
    success: (msg: string) => toast.success(msg, {
      style: {
        background: "#0f172a",
        color: "#e2e8f0",
        border: "1px solid rgba(52, 211, 153, 0.3)",
      },
      iconTheme: { primary: "#34d399", secondary: "#0f172a" },
    }),
    error: (msg: string) => toast.error(msg, {
      style: {
        background: "#0f172a",
        color: "#e2e8f0",
        border: "1px solid rgba(248, 113, 113, 0.3)",
      },
      iconTheme: { primary: "#f87171", secondary: "#0f172a" },
    }),
    info: (msg: string) => toast(msg, {
      style: {
        background: "#0f172a",
        color: "#e2e8f0",
        border: "1px solid rgba(103, 232, 249, 0.3)",
      },
      iconTheme: { primary: "#67e8f9", secondary: "#0f172a" },
    }),
    promise: <T>(promise: Promise<T>, messages: { loading: string; success: string; error: string }) =>
      toast.promise(promise, messages, {
        style: {
          background: "#0f172a",
          color: "#e2e8f0",
          border: "1px solid rgba(148, 163, 184, 0.2)",
        },
        success: {
          iconTheme: { primary: "#34d399", secondary: "#0f172a" },
        },
        error: {
          iconTheme: { primary: "#f87171", secondary: "#0f172a" },
        },
      }),
    dismiss: toast.dismiss,
  };
}

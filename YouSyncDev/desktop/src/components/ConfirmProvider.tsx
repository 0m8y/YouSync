import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

type ConfirmOptions = {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
};

type PendingConfirm = ConfirmOptions & {
  resolve: (confirmed: boolean) => void;
};

type ConfirmContextValue = {
  confirm: (options: ConfirmOptions) => Promise<boolean>;
};

const ConfirmContext = createContext<ConfirmContextValue | null>(null);

function ConfirmProvider({ children }: { children: ReactNode }) {
  const [pendingConfirm, setPendingConfirm] = useState<PendingConfirm | null>(null);

  const confirm = useCallback((options: ConfirmOptions) => (
    new Promise<boolean>((resolve) => {
      setPendingConfirm({ ...options, resolve });
    })
  ), []);

  const close = useCallback((confirmed: boolean) => {
    setPendingConfirm((current) => {
      current?.resolve(confirmed);
      return null;
    });
  }, []);

  const value = useMemo(() => ({ confirm }), [confirm]);

  return (
    <ConfirmContext.Provider value={value}>
      {children}
      {pendingConfirm ? (
        <div
          className="confirm-backdrop"
          role="presentation"
          onMouseDown={() => close(false)}
        >
          <div
            className="confirm-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="confirm-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <h2 id="confirm-title">{pendingConfirm.title}</h2>
            <p>{pendingConfirm.message}</p>
            <div className="confirm-actions">
              <button type="button" onClick={() => close(false)}>
                {pendingConfirm.cancelLabel ?? "Cancel"}
              </button>
              <button
                className={pendingConfirm.danger ? "danger" : ""}
                type="button"
                onClick={() => close(true)}
              >
                {pendingConfirm.confirmLabel ?? "Confirm"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </ConfirmContext.Provider>
  );
}

function useConfirm() {
  const context = useContext(ConfirmContext);

  if (!context) {
    throw new Error("useConfirm must be used inside ConfirmProvider.");
  }

  return context;
}

export { ConfirmProvider, useConfirm };

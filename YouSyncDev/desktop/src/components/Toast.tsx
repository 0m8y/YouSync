type ToastProps = {
  message: string;
};

function Toast({ message }: ToastProps) {
  return (
    <div className="toast" role="status">
      {message}
    </div>
  );
}

export default Toast;

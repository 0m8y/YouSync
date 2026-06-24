import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";

function AppShell() {
  return (
    <div className="ys-root">
      <Sidebar />
      <main className="ys-main">
        <Outlet />
      </main>
    </div>
  );
}

export default AppShell;

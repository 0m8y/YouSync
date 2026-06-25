import { NavLink } from "react-router-dom";

const navItems = [
  { label: "Sync Playlist", to: "/", icon: "♺" },
  { label: "Playlists", to: "/playlists", icon: "≡" },
  { label: "Settings", to: "/settings", icon: "⚙" }
];

function Sidebar() {
  return (
    <aside className="ys-sidebar" aria-label="Main navigation">

      <div className="ys-logo">
        <div className="ys-logo-icon" aria-hidden="true">♪</div>
        <span className="ys-logo-name">YouSync</span>
      </div>

      <nav className="ys-nav">
        {navItems.map((item) => (
          <NavLink
            className={({ isActive }) => `ys-nav-item${isActive ? " active" : ""}`}
            end={item.to === "/"}
            key={item.to}
            to={item.to}
          >
            <span className="ys-nav-icon" aria-hidden="true">{item.icon}</span>
            <span className="ys-nav-label">{item.label}</span>
            {item.count ? <span className="ys-nav-count">{item.count}</span> : null}
          </NavLink>
        ))}
      </nav>

      <div className="ys-sidebar-footer">
        <div className="version-pill">
          <span className="version-avatar" aria-hidden="true">•</span>
          <span>v1.0.0</span>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;

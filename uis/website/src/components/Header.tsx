export default function Header() {
  return (
    <header style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      padding: "20px 40px",
      borderBottom: "1px solid #e5e7eb",
      background: "#ffffff",
      position: "sticky",
      top: 0,
      zIndex: 10
    }}>
      <strong style={{ fontSize: "1.25rem" }}>TrackFlow</strong>

      <nav style={{ display: "flex", gap: "24px" }}>
        <a href="#services">Services</a>
        <a href="#why-trackflow">Why TrackFlow</a>
        <a href="#faq">FAQ</a>
        <a href="#contact">Contact</a>
      </nav>
    </header>
  );
}

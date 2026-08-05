export default function Footer() {
  return (
    <footer style={{
      padding: "36px 24px",
      background: "#111827",
      color: "#ffffff"
    }}>
      <div style={{
        maxWidth: 1100,
        margin: "0 auto",
        display: "flex",
        justifyContent: "space-between",
        gap: 24,
        flexWrap: "wrap"
      }}>
        <div>
          <strong style={{ fontSize: "1.2rem" }}>TrackFlow</strong>
          <p style={{ color: "#cbd5e1", marginTop: 8 }}>
            Logistics infrastructure for modern ecommerce brands.
          </p>
        </div>

        <div>
          <p style={{ margin: 0 }}>Los Angeles · Zaragoza</p>
          <p style={{ color: "#cbd5e1", marginTop: 8 }}>
            © 2026 TrackFlow. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  );
}

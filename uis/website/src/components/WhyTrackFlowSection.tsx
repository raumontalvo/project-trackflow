const reasons = [
  {
    title: "Unified logistics visibility",
    text: "Track inventory, shipments, carriers, and returns across the United States and Spain from one connected platform.",
  },
  {
    title: "Smarter operational decisions",
    text: "Use structured data and reusable business logic to reduce manual work and improve delivery performance.",
  },
  {
    title: "Built for modern ecommerce",
    text: "TrackFlow supports warehouse operations, last-mile delivery, reverse logistics, and customer experience at scale.",
  },
];

export default function WhyTrackFlowSection() {
  return (
    <section
      id="why-trackflow"
      style={{
        padding: "80px 24px",
        background: "#f6f8fc",
      }}
    >
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        <p style={{
          color: "#5266d5",
          fontWeight: 800,
          letterSpacing: "0.1em",
          textTransform: "uppercase",
          marginBottom: 8
        }}>
          Why TrackFlow
        </p>

        <h2 style={{ fontSize: "2.4rem", marginBottom: 16 }}>
          One logistics partner. One connected operation.
        </h2>

        <p style={{
          maxWidth: 720,
          color: "#667085",
          lineHeight: 1.7,
          marginBottom: 36
        }}>
          We help ecommerce brands remove operational complexity by connecting
          warehouse activity, delivery performance, returns, and customer support.
        </p>

        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
          gap: 20
        }}>
          {reasons.map((reason) => (
            <article
              key={reason.title}
              style={{
                padding: 24,
                border: "1px solid #e1e6ef",
                borderRadius: 16,
                background: "#ffffff"
              }}
            >
              <h3 style={{ marginBottom: 10 }}>{reason.title}</h3>
              <p style={{ color: "#667085", lineHeight: 1.6 }}>
                {reason.text}
              </p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

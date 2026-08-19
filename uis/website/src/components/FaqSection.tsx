const faqs = [
  {
    question: "What services does TrackFlow provide?",
    answer:
      "TrackFlow provides warehouse management, order fulfillment, last-mile delivery coordination, carrier management, and reverse logistics.",
  },
  {
    question: "Where does TrackFlow operate?",
    answer:
      "TrackFlow operates in the United States and Spain, with warehouse operations in Los Angeles and Zaragoza.",
  },
  {
    question: "Can TrackFlow support growing ecommerce brands?",
    answer:
      "Yes. TrackFlow is designed to help mid-sized ecommerce brands scale their logistics operation without building an internal logistics team.",
  },
  {
    question: "Does TrackFlow manage returns?",
    answer:
      "Yes. TrackFlow handles reverse logistics, including return coordination, inspection workflows, and inventory updates.",
  },
];

export default function FaqSection() {
  return (
    <section id="faq" style={{ padding: "80px 24px", background: "#ffffff" }}>
      <div style={{ maxWidth: 900, margin: "0 auto" }}>
        <p style={{
          color: "#5266d5",
          fontWeight: 800,
          letterSpacing: "0.1em",
          textTransform: "uppercase",
          marginBottom: 8
        }}>
          FAQ
        </p>

        <h2 style={{ fontSize: "2.4rem", marginBottom: 32 }}>
          Frequently asked questions
        </h2>

        <div style={{ display: "grid", gap: 16 }}>
          {faqs.map((faq) => (
            <details
              key={faq.question}
              style={{
                padding: 20,
                border: "1px solid #e1e6ef",
                borderRadius: 14,
                background: "#f9fafb"
              }}
            >
              <summary style={{ cursor: "pointer", fontWeight: 700 }}>
                {faq.question}
              </summary>

              <p style={{
                color: "#667085",
                lineHeight: 1.7,
                marginTop: 14
              }}>
                {faq.answer}
              </p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

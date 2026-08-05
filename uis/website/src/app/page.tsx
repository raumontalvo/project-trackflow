import Header from "../components/Header";
import HeroSection from "../components/HeroSection";
import ServicesSection from "../components/ServicesSection";
import CoverageSection from "../components/CoverageSection";
import WhyTrackFlowSection from "../components/WhyTrackFlowSection";
import FaqSection from "../components/FaqSection";
import ContactSection from "../components/ContactSection";
import Footer from "../components/Footer";

export default function Home() {
  return (
    <>
      <Header />

      <main>
        <HeroSection />
        <ServicesSection />
        <CoverageSection />
        <WhyTrackFlowSection />
        <FaqSection />
        <ContactSection />
      </main>

      <Footer />
    </>
  );
}

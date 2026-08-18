import HeroSection from "../components/HeroSection";
import ServicesSection from "../components/ServicesSection";
import CoverageSection from "../components/CoverageSection";
import ChatSection from "../components/ChatSection";
import ContactSection from "../components/ContactSection";

export default function Home() {
  return (
    <main>
      <HeroSection />
      <ServicesSection />
      <CoverageSection />
      <ChatSection />
      <ContactSection />
    </main>
  );
}
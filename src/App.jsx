import Navbar from "./components/Navbar.jsx";
import Footer from "./components/Footer.jsx";
import Hero from "./sections/Hero.jsx";
import MeetJuris from "./sections/MeetJuris.jsx";
import WhyJuris from "./sections/WhyJuris.jsx";
import Features from "./sections/Features.jsx";
import Workflow from "./sections/Workflow.jsx";
import Advantages from "./sections/Advantages.jsx";
import ProductPreview from "./sections/ProductPreview.jsx";
import FinalCta from "./sections/FinalCta.jsx";

export default function App() {
  return (
    <>
      <Navbar />
      <main>
        <Hero />
        <MeetJuris />
        <WhyJuris />
        <Features />
        <Workflow />
        <Advantages />
        <ProductPreview />
        <FinalCta />
      </main>
      <Footer />
    </>
  );
}

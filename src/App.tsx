import { motion } from "framer-motion";
import Navbar from "./components/Navbar.jsx";
import Footer from "./components/Footer.jsx";
import Hero from "./sections/Hero.jsx";
import MeetJuris from "./sections/MeetJuris.jsx";
import WhyJuris from "./sections/WhyJuris.jsx";
import Features from "./sections/Features.jsx";
import HowToUse from "./sections/HowToUse.jsx";
import Workflow from "./sections/Workflow.jsx";
import Advantages from "./sections/Advantages.jsx";
import ProductPreview from "./sections/ProductPreview.jsx";
import FinalCta from "./sections/FinalCta.jsx";

export default function App() {
  return (
    <motion.div
      className="site-page"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.45 }}
    >
      <Navbar />
      <main>
        <Hero />
        <MeetJuris />
        <WhyJuris />
        <Features />
        <HowToUse />
        <Workflow />
        <Advantages />
        <ProductPreview />
        <FinalCta />
      </main>
      <Footer />
    </motion.div>
  );
}

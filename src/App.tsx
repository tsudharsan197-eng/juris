import { motion } from "framer-motion";
import Navbar from "./components/Navbar.jsx";
import Footer from "./components/Footer.jsx";
import ScrollDirector from "./components/ScrollDirector";
import MobileScrollDirector from "./components/MobileScrollDirector";
import Hero from "./sections/Hero.jsx";
import MeetJuris from "./sections/MeetJuris.jsx";
import WhyJuris from "./sections/WhyJuris.jsx";
import Features from "./sections/Features.jsx";
import Workflow from "./sections/Workflow.jsx";
import Advantages from "./sections/Advantages.jsx";
import ProductPreview from "./sections/ProductPreview.jsx";

export default function App() {
  return (
    <motion.div
      className="site-page"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.45 }}
    >
      <Navbar />
      <ScrollDirector />
      <MobileScrollDirector />
      <main>
        <Hero />
        <MeetJuris />
        <WhyJuris />
        <Features />
        <Workflow />
        <Advantages />
        <ProductPreview />
      </main>
      <Footer />
    </motion.div>
  );
}

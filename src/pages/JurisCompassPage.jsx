import Navbar from "../components/Navbar.jsx";
import JurisCompass from "../components/JurisCompass.jsx";

export default function JurisCompassPage() {
  return (
    <>
      <Navbar />
      <main className="compass-page">
        <JurisCompass />
      </main>
    </>
  );
}

import Login from "./pages/Login";
import "./styles.css";

export default function LoginPreview() {
  return (
    <Login
      onLogin={({ identifier }) => {
        alert(
          `Prévisualisation uniquement : ${identifier}`
        );
      }}
    />
  );
}
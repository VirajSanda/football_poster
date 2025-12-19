import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "./App";

test("renders brand title", () => {
  render(
    <MemoryRouter initialEntries={["/posts"]}>
      <App />
    </MemoryRouter>
  );

  const brand = screen.getByText(/KickOffZone/i);
  expect(brand).toBeInTheDocument();
});

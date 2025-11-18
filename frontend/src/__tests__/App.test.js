import React from "react";
import { render, screen } from "@testing-library/react";
import App from "../App";

test("renders app and shows brand title", () => {
  render(<App />);
  const brand = screen.getByText(/KickOffZone/i);
  expect(brand).toBeInTheDocument();
});

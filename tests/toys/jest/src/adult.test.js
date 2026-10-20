const { spec } = require("../redline/runners/jest");
const { adult } = require("./adult");

spec("TOY.H1").test("a grown-up is an adult", () => {
  expect(adult(30)).toBe(true);
});

spec("TOY.H2").test("an adult starts at 18", () => {
  expect(adult(18)).toBe(true);
  expect(adult(17)).toBe(false);
});

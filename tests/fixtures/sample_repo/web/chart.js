// Render a bar chart of monthly sales figures on a canvas.
export function drawBarChart(canvas, values) {
  const ctx = canvas.getContext("2d");
  const width = canvas.width / values.length;
  values.forEach((v, i) => {
    ctx.fillStyle = "#3b82f6";
    ctx.fillRect(i * width, canvas.height - v, width - 4, v);
  });
}

export function formatCurrency(amount) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(amount);
}

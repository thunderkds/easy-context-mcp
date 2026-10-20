const LOCALE = "en-US";

function formatMoney(amount) {
  return new Intl.NumberFormat(LOCALE, { style: "currency", currency: "USD" }).format(amount);
}

const formatDate = function (d) {
  return d.toISOString().slice(0, 10);
};

class Formatter {
  constructor(prefix) {
    this.prefix = prefix;
  }

  line(text) {
    return this.prefix + text;
  }
}

module.exports = { formatMoney, formatDate, Formatter };

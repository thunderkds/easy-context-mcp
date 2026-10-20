import { Price } from "./price";

export interface CartLine {
  sku: string;
  qty: number;
}

/** Sum of all line prices. */
export function cartTotal(lines: CartLine[], price: Price): number {
  return lines.reduce((sum, l) => sum + price(l.sku) * l.qty, 0);
}

export const emptyCart = (): CartLine[] => [];

export default function checkout(lines: CartLine[]): string {
  return `paid ${lines.length}`;
}

export class Cart {
  lines: CartLine[] = [];

  add(line: CartLine): void {
    this.lines.push(line);
  }

  clear(): void {
    this.lines = [];
  }
}

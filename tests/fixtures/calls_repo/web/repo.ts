import { formatTotal } from "./fmt";

interface Persist {
  save(): void;
}

class BaseRepo {}

export class Repo extends BaseRepo implements Persist {
  add(): void {
    this.save();
  }

  save(): void {}
}

export function checkout(r: Repo): string {
  r.add();
  return formatTotal(1);
}

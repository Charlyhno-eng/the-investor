export type BankAccount = { id: string; name: string; balance: number };
export const bankAccountsKey = "investor-bank-accounts";

export function readBankAccounts(): BankAccount[] {
  try {
    const saved: unknown = JSON.parse(
      localStorage.getItem(bankAccountsKey) ?? "[]",
    );
    if (!Array.isArray(saved)) return [];
    const ids = new Set<string>();
    return saved.filter((account): account is BankAccount => {
      if (
        !account ||
        typeof account !== "object" ||
        typeof account.id !== "string" ||
        !account.id ||
        ids.has(account.id) ||
        typeof account.name !== "string" ||
        !account.name.trim() ||
        typeof account.balance !== "number" ||
        !Number.isFinite(account.balance) ||
        Math.abs(account.balance) > 1e15
      )
        return false;
      ids.add(account.id);
      return true;
    });
  } catch {
    return [];
  }
}

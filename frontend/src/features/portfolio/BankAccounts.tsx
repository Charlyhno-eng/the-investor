import { useState, type FormEvent } from "react";
import { money } from "../../lib/currency";
import type { BankAccount } from "./bankAccounts";

export function BankAccounts({
  accounts,
  onChange,
}: {
  accounts: BankAccount[];
  onChange: (accounts: BankAccount[]) => void;
}) {
  const [editing, setEditing] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [balance, setBalance] = useState("");
  function reset() {
    setEditing(null);
    setName("");
    setBalance("");
  }
  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim() || !balance.trim() || !Number.isFinite(Number(balance)))
      return;
    const account = {
      id: editing ?? crypto.randomUUID(),
      name: name.trim(),
      balance: Number(balance),
    };
    onChange(
      editing
        ? accounts.map((item) => (item.id === editing ? account : item))
        : [...accounts, account],
    );
    reset();
  }
  return (
    <section className="portfolio-content" aria-label="Comptes bancaires">
      <div className="portfolio-section-heading">
        <div>
          <h2>Vos comptes bancaires</h2>
          <p>
            Suivez vos soldes en euros. Ces montants sont exclus des analyses et
            des stratégies d’investissement.
          </p>
        </div>
        <span className="fine-print">Enregistrés sur ce navigateur</span>
      </div>
      <form className="bank-account-form" onSubmit={save}>
        <label>
          Nom du compte
          <input
            required
            maxLength={100}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Ex. Compte courant"
          />
        </label>
        <label>
          Solde (€)
          <input
            required
            type="number"
            step="0.01"
            min={-1e15}
            max={1e15}
            value={balance}
            onChange={(e) => setBalance(e.target.value)}
            placeholder="0,00"
          />
        </label>
        <button className="secondary-button" type="submit">
          {editing ? "Enregistrer" : "Ajouter le compte"}
        </button>
        {editing && (
          <button className="secondary-button" type="button" onClick={reset}>
            Annuler
          </button>
        )}
      </form>
      {!accounts.length ? (
        <p className="portfolio-empty">
          Ajoutez votre premier compte bancaire pour suivre votre patrimoine
          total.
        </p>
      ) : (
        <ul className="bank-account-list">
          {accounts.map((account) => (
            <li key={account.id}>
              <span>{account.name}</span>
              <strong>{money(account.balance)}</strong>
              <button
                className="secondary-button"
                aria-label={`Modifier ${account.name}`}
                onClick={() => {
                  setEditing(account.id);
                  setName(account.name);
                  setBalance(String(account.balance));
                }}
              >
                Modifier
              </button>
              <button
                className="secondary-button"
                aria-label={`Supprimer ${account.name}`}
                onClick={() => {
                  onChange(accounts.filter((item) => item.id !== account.id));
                  if (editing === account.id) reset();
                }}
              >
                Supprimer
              </button>
            </li>
          ))}
        </ul>
      )}
      <p className="bank-account-total">
        Total des comptes{" "}
        <strong>
          {money(accounts.reduce((sum, account) => sum + account.balance, 0))}
        </strong>
      </p>
    </section>
  );
}

import { useState } from "react";
import { Icon } from "../../components/Icon";
import type { Asset } from "../../lib/types";
import { PortfolioPanel } from "./PortfolioPanel";
import type { StrategyStore as Store } from "./useStrategies";

export function StrategyLibrary({ store }: { store: Store }) {
  const [name, setName] = useState("");
  return (
    <aside className="asset-library strategy-library">
      <div className="library-heading">
        <h2>Stratégies</h2>
      </div>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (name.trim()) {
            store.create(name);
            setName("");
          }
        }}
      >
        <label htmlFor="strategy-name">Nouvelle stratégie</label>
        <input
          id="strategy-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Nom de la stratégie"
          maxLength={80}
          required
        />
        <button className="secondary-button" type="submit">
          Créer une stratégie
        </button>
      </form>
      <div className="strategy-list">
        {store.strategies.map((strategy) => (
          <button
            key={strategy.id}
            className={store.selected?.id === strategy.id ? "selected" : ""}
            aria-pressed={store.selected?.id === strategy.id}
            onClick={() => store.select(strategy.id)}
          >
            {strategy.name}
            <small>
              {Object.keys(strategy.quantities).length}{" "}
              {Object.keys(strategy.quantities).length === 1
                ? "actif"
                : "actifs"}
            </small>
          </button>
        ))}
      </div>
    </aside>
  );
}
export function StrategyWorkspace({
  store,
  assets,
  eligibleAssetIds,
  onImport,
}: {
  store: Store;
  assets: Asset[];
  eligibleAssetIds: string[];
  onImport: () => void;
}) {
  const [assetId, setAssetId] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const strategy = store.selected;
  const categoryOrder = (asset: Asset) =>
    asset.category === "stock" ? 0 : asset.category === "crypto" ? 1 : 2;
  const available = assets
    .filter(
      (asset) =>
        eligibleAssetIds.includes(asset.id) &&
        (!strategy || !(asset.id in strategy.quantities)),
    )
    .sort(
      (a, b) =>
        categoryOrder(a) - categoryOrder(b) ||
        a.name.localeCompare(b.name, "fr"),
    );
  return (
    <>
      {store.error && (
        <p className="error" role="alert">
          {store.error}
        </p>
      )}
      {!strategy ? (
        <div className="workspace-empty">
          <h1>Stratégie</h1>
          <p>
            Créez une stratégie pour simuler un portefeuille avec les actifs de
            votre watchlist ou de votre portfolio.
          </p>
        </div>
      ) : (
        <>
          <PortfolioPanel
            key={strategy.id}
            title={strategy.name}
            simulation
            positionsHeader={
              <>
                <div className="strategy-toolbar">
                  <div className="strategy-toolbar-heading">
                    <div>
                      <h2>Composer la stratégie</h2>
                      <p>
                        Ajoutez les actifs de votre watchlist ou de votre
                        portfolio, puis ajustez leurs quantités.
                      </p>
                    </div>
                    <div className="strategy-management">
                      {confirmDelete === strategy.id ? (
                        <div
                          className="strategy-delete-confirm"
                          role="group"
                          aria-label="Confirmer la suppression"
                        >
                          <span>Supprimer « {strategy.name} » ?</span>
                          <button
                            className="secondary-button"
                            onClick={() => {
                              store.remove(strategy.id);
                              setConfirmDelete(null);
                            }}
                          >
                            Confirmer la suppression
                          </button>
                          <button
                            className="secondary-button"
                            onClick={() => setConfirmDelete(null)}
                          >
                            Annuler
                          </button>
                        </div>
                      ) : (
                        <button
                          className="secondary-button strategy-delete"
                          onClick={() => setConfirmDelete(strategy.id)}
                        >
                          Supprimer la stratégie
                        </button>
                      )}
                    </div>
                  </div>
                  <form
                    onSubmit={(event) => {
                      event.preventDefault();
                      const id = available.some((a) => a.id === assetId)
                        ? assetId
                        : available[0]?.id;
                      if (id) {
                        store.update({
                          ...strategy,
                          quantities: { ...strategy.quantities, [id]: 0 },
                        });
                        setAssetId("");
                      }
                    }}
                  >
                    <div className="strategy-watchlist-field">
                      <label htmlFor="strategy-asset">
                        <Icon name="star" size={14} /> Ajouter un actif{" "}
                        <span>· Watchlist et portfolio</span>
                      </label>
                      <select
                        id="strategy-asset"
                        aria-label="Ajouter un actif"
                        value={
                          available.some((a) => a.id === assetId)
                            ? assetId
                            : (available[0]?.id ?? "")
                        }
                        onChange={(e) => setAssetId(e.target.value)}
                        disabled={!available.length}
                      >
                        {!available.length && (
                          <option value="">
                            {eligibleAssetIds.length
                              ? "Tous les actifs sont ajoutés"
                              : "Aucun actif disponible"}
                          </option>
                        )}
                        {available.map((asset) => (
                          <option key={asset.id} value={asset.id}>
                            {asset.name}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="strategy-add-actions">
                      <button
                        className="primary-button"
                        disabled={!available.length}
                      >
                        <Icon name="plus" size={15} /> Ajouter
                      </button>
                      <button
                        className="primary-button"
                        type="button"
                        onClick={onImport}
                      >
                        <Icon name="plus" size={15} /> Importer un actif
                      </button>
                    </div>
                  </form>
                  {!available.length && (
                    <p className="strategy-watchlist-note">
                      {eligibleAssetIds.length
                        ? "Tous les actifs de votre watchlist et de votre portfolio sont déjà dans cette stratégie."
                        : "Votre watchlist et votre portfolio sont vides. Ajoutez-y des actifs depuis la bibliothèque pour les retrouver ici."}
                    </p>
                  )}
                </div>
                {!!Object.keys(strategy.quantities).length && (
                  <div
                    className="strategy-assets"
                    aria-label="Actifs de la stratégie"
                  >
                    {Object.keys(strategy.quantities).map((id) => (
                      <button
                        key={id}
                        title="Retirer de la stratégie"
                        disabled={strategy.lockedAssetIds.includes(id)}
                        onClick={() => {
                          const quantities = { ...strategy.quantities };
                          delete quantities[id];
                          store.update({
                            ...strategy,
                            quantities,
                            lockedAssetIds: strategy.lockedAssetIds.filter(
                              (lockedId) => lockedId !== id,
                            ),
                          });
                        }}
                      >
                        {" "}
                        {assets.find((a) => a.id === id)?.name ?? id}{" "}
                        <span aria-hidden="true">×</span>
                        <span className="sr-only">Retirer de la stratégie</span>
                      </button>
                    ))}
                  </div>
                )}
              </>
            }
            assets={assets.filter((a) => a.id in strategy.quantities)}
            quantities={strategy.quantities}
            lockedAssetIds={strategy.lockedAssetIds}
            onToggleLock={(id) =>
              store.update({
                ...strategy,
                lockedAssetIds: strategy.lockedAssetIds.includes(id)
                  ? strategy.lockedAssetIds.filter((value) => value !== id)
                  : [...strategy.lockedAssetIds, id],
              })
            }
            onQuantity={(id, quantity) =>
              !strategy.lockedAssetIds.includes(id) &&
              store.update({
                ...strategy,
                quantities: { ...strategy.quantities, [id]: quantity },
              })
            }
          />
        </>
      )}
    </>
  );
}

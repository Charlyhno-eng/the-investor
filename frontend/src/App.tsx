import { useStrategies } from "./features/portfolio/useStrategies";
import {
  StrategyLibrary,
  StrategyWorkspace,
} from "./features/portfolio/Strategies";
import { WatchlistPanel } from "./features/portfolio/WatchlistPanel";
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { Icon } from "./components/Icon";
import { AssetLibrary } from "./features/assets/AssetLibrary";
import { AssetDetail } from "./features/assets/AssetDetail";
import { ImportDialog } from "./features/assets/ImportDialog";
import { api } from "./lib/api";
import { categories } from "./lib/format";
import type { Asset, Category } from "./lib/types";
import {
  readFavorites,
  isLibrary,
  type Library,
  type Favorites,
} from "./lib/favorites";
import { PortfolioPanel } from "./features/portfolio/PortfolioPanel";
import {
  readQuantities,
  type Quantities,
} from "./features/portfolio/quantities";
export function App() {
  const strategies = useStrategies();
  const { id, categoryId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const library = searchParams.get("library");
  const [assets, setAssets] = useState<Asset[]>([]),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  const [category, setCategory] = useState<Category | Library | "strategy">(
      isLibrary(library) ? library : id ? "stock" : "portfolio",
    ),
    [adding, setAdding] = useState(false),
    [revision, setRevision] = useState(0);
  const [favorites, setFavorites] = useState<Favorites>(readFavorites);
  const [removedAssets, setRemovedAssets] = useState<string[]>(() => {
    try {
      const saved: unknown = JSON.parse(
        localStorage.getItem("investor-removed-assets") ?? "[]",
      );
      return Array.isArray(saved)
        ? saved.filter((id): id is string => typeof id === "string")
        : [];
    } catch {
      return [];
    }
  });
  function removeAsset(id: string) {
    const next = [...removedAssets, id];
    setRemovedAssets(next);
    try {
      localStorage.setItem("investor-removed-assets", JSON.stringify(next));
      setFavoriteError("");
    } catch {
      setFavoriteError(
        "Le retrait reste effectif dans cette session, mais son enregistrement local a échoué.",
      );
    }
    navigate(`/markets/${category}`);
  }
  const visibleAssets = assets.filter(
    (asset) => !removedAssets.includes(asset.id),
  );
  const [quantities, setQuantities] = useState<Quantities>(readQuantities);
  function updateQuantity(id: string, quantity: number) {
    const next = { ...quantities, [id]: quantity };
    setQuantities(next);
    try {
      localStorage.setItem("investor-quantities", JSON.stringify(next));
      setFavoriteError("");
    } catch {
      setFavoriteError(
        "Les quantités n’ont pas pu être enregistrées ; elles restent disponibles dans cette session.",
      );
    }
  }
  const [favoriteError, setFavoriteError] = useState("");
  function toggleFavorite(id: string) {
    const next = { ...favorites };
    if (next[id] === "silver") delete next[id];
    else next[id] = next[id] === "gold" ? "silver" : "gold";
    setFavorites(next);
    try {
      localStorage.setItem("investor-favorites", JSON.stringify(next));
      setFavoriteError("");
    } catch {
      setFavoriteError(
        "Les favoris restent disponibles dans cette session, mais leur enregistrement local a échoué.",
      );
    }
  }
  const refresh = useCallback(() => setRevision((v) => v + 1), []);
  const imported = useCallback((assetId: string) => {
    setRemovedAssets((current) => {
      const next = current.filter((id) => id !== assetId);
      try {
        localStorage.setItem("investor-removed-assets", JSON.stringify(next));
      } catch {
        setFavoriteError(
          "L’action est restaurée pour cette session, mais son enregistrement local a échoué.",
        );
      }
      return next;
    });
    setRevision((v) => v + 1);
  }, []);
  const close = useCallback(() => setAdding(false), []);
  useEffect(() => {
    const controller = new AbortController();
    setError("");
    api<Asset[]>("/assets", { signal: controller.signal })
      .then(setAssets)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [revision]);
  // Poll only the local catalogue so queued imports appear after the dialog is closed.
  useEffect(() => {
    const interval = setInterval(refresh, 15000);
    return () => clearInterval(interval);
  }, [refresh]);
  const selected = visibleAssets.find((a) => a.id === id);
  const selectedCategory = selected?.category;
  useEffect(() => {
    if (selectedCategory)
      setCategory((current) =>
        isLibrary(library)
          ? library
          : isLibrary(current)
            ? current
            : selectedCategory,
      );
  }, [selectedCategory, library]);
  useEffect(() => {
    if (
      categoryId === "strategy" ||
      isLibrary(categoryId) ||
      categories.some((c) => c.id === categoryId)
    )
      setCategory(categoryId as Category | Library | "strategy");
    else if (!id) setCategory("portfolio");
  }, [categoryId, id]);
  function choose(value: Category | Library | "strategy") {
    setCategory(value);
    navigate(`/markets/${value}`);
  }
  return (
    <div className="app-shell">
      <header className="app-header">
        <Link to="/" className="brand">
          <span className="brand-mark">
            <i />
            <i />
            <i />
          </span>
          the investor<span className="brand-period">.</span>
        </Link>
        <div className="header-workspace">
          <span>Workspace</span>
          <span className="header-slash">/</span>
          <strong>Marchés</strong>
        </div>
      </header>
      <div className="app-body">
        <nav className="category-rail" aria-label="Catégories d’actifs">
          {(["portfolio", "watchlist"] as const).map((view) => (
            <button
              key={view}
              aria-label={view === "portfolio" ? "Portfolio" : "Watchlist"}
              className={category === view ? "active" : ""}
              onClick={() => choose(view)}
              aria-pressed={category === view}
              title={view === "portfolio" ? "Portfolio" : "Watchlist"}
            >
              <Icon name={view === "portfolio" ? "layers" : "star"} size={21} />
              <span>{view === "portfolio" ? "Portfolio" : "Watchlist"}</span>
              <span className="rail-count">
                {
                  visibleAssets.filter(
                    (a) =>
                      favorites[a.id] ===
                      (view === "portfolio" ? "gold" : "silver"),
                  ).length
                }
              </span>
            </button>
          ))}
          <div className="rail-divider" role="separator" />
          <button
            aria-label="Stratégie"
            title="Stratégie"
            className={category === "strategy" ? "active" : ""}
            aria-pressed={category === "strategy"}
            onClick={() => choose("strategy")}
          >
            <Icon name="analysis" size={21} />
            <span>Stratégie</span>
            <span className="rail-count">{strategies.strategies.length}</span>
          </button>
          <div className="rail-divider" role="separator" />
          {categories.map((c) => (
            <button
              key={c.id}
              aria-label={c.name}
              className={category === c.id ? "active" : ""}
              onClick={() => choose(c.id)}
              aria-pressed={category === c.id}
              title={c.name}
            >
              <Icon name={c.icon} size={21} />
              <span>{c.short}</span>
              <span className="rail-count">
                {visibleAssets.filter((a) => a.category === c.id).length}
              </span>
            </button>
          ))}
        </nav>
        {category === "strategy" ? (
          <StrategyLibrary store={strategies} />
        ) : (
          <AssetLibrary
            favorites={favorites}
            onToggleFavorite={toggleFavorite}
            assets={visibleAssets}
            category={category}
            selected={id}
            loading={loading}
            error={error}
            onAdd={() => setAdding(true)}
            onRetry={refresh}
          />
        )}
        <main className="main-workspace">
          {favoriteError && (
            <p role="alert" className="error">
              {favoriteError}
            </p>
          )}
          {category === "strategy" && !selected ? (
            <StrategyWorkspace
              store={strategies}
              eligibleAssetIds={visibleAssets
                .filter(
                  (a) =>
                    favorites[a.id] === "silver" || favorites[a.id] === "gold",
                )
                .map((a) => a.id)}
              assets={visibleAssets}
              onImport={() => setAdding(true)}
            />
          ) : selected ? (
            <AssetDetail
              key={selected.id}
              asset={selected}
              favorite={favorites[selected.id]}
              onToggleFavorite={() => toggleFavorite(selected.id)}
              onRemove={() => removeAsset(selected.id)}
            />
          ) : category === "watchlist" ? (
            <WatchlistPanel
              assets={visibleAssets.filter((a) => favorites[a.id] === "silver")}
            />
          ) : category === "portfolio" ? (
            <PortfolioPanel
              assets={visibleAssets
                .filter((a) => favorites[a.id] === "gold")
                .sort(
                  (a, b) =>
                    categories.findIndex((c) => c.id === a.category) -
                    categories.findIndex((c) => c.id === b.category),
                )}
              quantities={quantities}
              onQuantity={updateQuantity}
            />
          ) : (
            <div className="workspace-empty">
              <Icon name="layers" size={36} />
              <h1>
                {loading
                  ? "Chargement des marchés…"
                  : "Votre espace de recherche"}
              </h1>
              <p>
                {error ||
                  "Choisissez un actif dans la bibliothèque pour consulter son historique."}
              </p>
              <button className="secondary-button" onClick={refresh}>
                Actualiser
              </button>
            </div>
          )}
        </main>
      </div>
      {adding && (
        <ImportDialog
          close={close}
          onImported={imported}
          removedAssets={removedAssets}
        />
      )}
    </div>
  );
}

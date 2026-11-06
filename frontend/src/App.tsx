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
import {
  PortfolioPanel,
  readQuantities,
  type Quantities,
} from "./features/portfolio/PortfolioPanel";
export function App() {
  const { id, categoryId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const library = searchParams.get("library");
  const [assets, setAssets] = useState<Asset[]>([]),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  const [category, setCategory] = useState<Category | Library>(
      isLibrary(library) ? library : "stock",
    ),
    [adding, setAdding] = useState(false),
    [revision, setRevision] = useState(0);
  const [favorites, setFavorites] = useState<Favorites>(readFavorites);
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
  const selected = assets.find((a) => a.id === id);
  useEffect(() => {
    if (selected)
      setCategory((current) =>
        isLibrary(library)
          ? library
          : isLibrary(current)
            ? current
            : selected.category,
      );
  }, [selected?.id, library]);
  useEffect(() => {
    if (isLibrary(categoryId) || categories.some((c) => c.id === categoryId))
      setCategory(categoryId as Category | Library);
  }, [categoryId]);
  function choose(value: Category | Library) {
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
        <div className="header-actions">
          <span className="local-label">
            <span className="status-dot" />
            Données locales
          </span>
          <button className="secondary-button" onClick={() => setAdding(true)}>
            <Icon name="plus" size={15} />
            <span>Ajouter une action</span>
          </button>
        </div>
      </header>
      <div className="app-body">
        <nav className="category-rail" aria-label="Catégories d’actifs">
          {(["portfolio", "watchlist"] as const).map((view) => (
            <button
              key={view}
              className={category === view ? "active" : ""}
              onClick={() => choose(view)}
              aria-pressed={category === view}
              title={view === "portfolio" ? "Portfolio" : "Watchlist"}
            >
              <Icon name={view === "portfolio" ? "layers" : "star"} size={21} />
              <span>{view === "portfolio" ? "Portfolio" : "Watchlist"}</span>
            </button>
          ))}
          <div className="rail-divider" role="separator" />
          {categories.map((c) => (
            <button
              key={c.id}
              className={category === c.id ? "active" : ""}
              onClick={() => choose(c.id)}
              aria-pressed={category === c.id}
              title={c.name}
            >
              <Icon name={c.icon} size={21} />
              <span>{c.short}</span>
            </button>
          ))}
          <div className="rail-bottom">
            <Icon name="layers" size={20} />
            <span>v0.2</span>
          </div>
        </nav>
        <AssetLibrary
          favorites={favorites}
          onToggleFavorite={toggleFavorite}
          assets={assets}
          category={category}
          selected={id}
          loading={loading}
          error={error}
          onAdd={() => setAdding(true)}
          onRetry={refresh}
        />
        <main className="main-workspace">
          {favoriteError && (
            <p role="alert" className="error">
              {favoriteError}
            </p>
          )}
          {selected ? (
            <AssetDetail
              key={selected.id}
              asset={selected}
              quantity={quantities[selected.id] ?? 0}
              onQuantity={(value) => updateQuantity(selected.id, value)}
              favorite={favorites[selected.id]}
              onToggleFavorite={() => toggleFavorite(selected.id)}
            />
          ) : category === "portfolio" ? (
            <PortfolioPanel
              assets={assets.filter((a) => favorites[a.id] === "gold")}
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
      {adding && <ImportDialog close={close} refresh={refresh} />}
    </div>
  );
}

import { Fragment, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { stockCountry } from "../../lib/countries";
import { Tooltip } from "../../components/Tooltip";
import { Icon } from "../../components/Icon";
import { categories, date, number } from "../../lib/format";
import type { Asset, Category } from "../../lib/types";
import {
  favoriteLabel,
  isLibrary,
  type Library,
  favoriteRank,
  type Favorites,
} from "../../lib/favorites";
export function AssetLibrary({
  assets,
  favorites,
  onToggleFavorite,
  category,
  selected,
  loading,
  error,
  onAdd,
  onRetry,
}: {
  assets: Asset[];
  category: Category | Library;
  favorites: Favorites;
  onToggleFavorite: (id: string) => void;
  selected?: string;
  loading: boolean;
  error: string;
  onAdd: () => void;
  onRetry: () => void;
}) {
  const [query, setQuery] = useState("");
  const [dividendOnly, setDividendOnly] = useState(false);
  const list = useRef<HTMLElement>(null);
  const search = useRef<HTMLInputElement>(null);
  useEffect(() => setQuery(""), [category]);
  useEffect(() => {
    const focus = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (
        event.key === "/" &&
        !["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName) &&
        !target.isContentEditable
      ) {
        event.preventDefault();
        search.current?.focus();
      }
    };
    window.addEventListener("keydown", focus);
    return () => window.removeEventListener("keydown", focus);
  }, []);
  const filtered = assets.filter(
    (a) =>
      (category === "portfolio"
        ? favorites[a.id] === "gold"
        : category === "watchlist"
          ? favorites[a.id] === "silver"
          : a.category === category) &&
      (category !== "stock" || !dividendOnly || !!a.is_dividend) &&
      `${a.name} ${a.id} ${a.country_code ?? ""}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  if (category === "bond")
    filtered.sort(
      (a, b) =>
        (b.year_average_yield ?? -Infinity) -
          (a.year_average_yield ?? -Infinity) || a.name.localeCompare(b.name),
    );
  filtered.sort(
    (a, b) => favoriteRank(favorites[b.id]) - favoriteRank(favorites[a.id]),
  );
  if (isLibrary(category))
    filtered.sort(
      (a, b) =>
        categories.findIndex((c) => c.id === a.category) -
        categories.findIndex((c) => c.id === b.category),
    );
  const total = assets.filter(
    (a) =>
      (category !== "stock" || !dividendOnly || !!a.is_dividend) &&
      (category === "portfolio"
        ? favorites[a.id] === "gold"
        : category === "watchlist"
          ? favorites[a.id] === "silver"
          : a.category === category),
  ).length;
  return (
    <aside className="asset-library">
      <div className="library-heading">
        <span className="eyebrow">BIBLIOTHÈQUE</span>
        <button
          className="icon-button"
          onClick={onAdd}
          aria-label="Ajouter une action"
        >
          <Icon name="plus" size={16} />
        </button>
      </div>
      <h2>
        {isLibrary(category)
          ? category === "portfolio"
            ? "Portfolio"
            : "Watchlist"
          : categories.find((c) => c.id === category)?.name}
        <span>{total}</span>
      </h2>
      {category === "portfolio" && (
        <Link className="portfolio-overview-link" to="/markets/portfolio">
          Vue d’ensemble du Portfolio
        </Link>
      )}
      <label className="library-search">
        <Icon name="search" size={15} />
        <input
          ref={search}
          aria-label="Rechercher un actif local"
          placeholder="Rechercher un actif"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <kbd>/</kbd>
      </label>
      <div className="list-heading">
        <span>ACTIF</span>
        <span>{category === "bond" ? "MOY. 12 M ↓" : "DERNIER"}</span>
      </div>
      {category === "stock" && (
        <button
          className="secondary-button dividend-library-filter"
          aria-pressed={dividendOnly}
          onClick={() => setDividendOnly((value) => !value)}
        >
          Dividendes uniquement
        </button>
      )}
      {category === "bond" && (
        <div className="ranking-note">
          Rendement moyen décroissant{" "}
          <Tooltip label="Classement sur douze mois">
            Moyenne des taux annualisés disponibles sur les douze mois se
            terminant à la dernière observation souveraine du catalogue. Ce taux
            n’est ni un coupon ni la performance réalisée sur un an. Les pays
            sans observation récente sont placés en fin de liste ; devises et
            risques diffèrent.
          </Tooltip>
        </div>
      )}
      <nav ref={list} aria-label="Actifs" className="asset-list">
        {filtered.map((a, index) => (
          <Fragment key={a.id}>
            {isLibrary(category) &&
              index > 0 &&
              filtered[index - 1].category !== a.category && (
                <div className="asset-category-divider" role="separator" />
              )}
            <div className="asset-list-item">
              <Link
                title={
                  a.category === "bond"
                    ? `${a.name} · moyenne sur ${a.year_yield_samples} observation(s) · dernière donnée ${date(a.last_date)}`
                    : a.name
                }
                to={`/assets/${a.id}${isLibrary(category) ? `?library=${category}` : ""}`}
                aria-current={selected === a.id ? "page" : undefined}
              >
                <span className={`list-symbol ${a.category}`}>
                  {a.country_code ??
                    (a.id.startsWith("yf-")
                      ? a.id.slice(3).split("-")[0].slice(0, 3).toUpperCase()
                      : a.name.slice(0, 2))}
                </span>
                <span className="list-name">
                  <strong>
                    {a.name}
                    {a.category === "stock" && !!a.is_dividend && (
                      <span
                        className="dividend-list-badge"
                        title="Action à dividende"
                        aria-label="Action à dividende"
                      >
                        D
                      </span>
                    )}
                  </strong>
                  <small>
                    {a.id.startsWith("yf-")
                      ? a.id.slice(3).toUpperCase()
                      : a.metric === "yield"
                        ? "Souverain · %"
                        : a.unit}
                    {a.category === "stock" && ` · ${stockCountry(a)}`}
                  </small>
                </span>
                <span className="list-value">
                  {a.category === "bond"
                    ? a.year_average_yield == null
                      ? "—"
                      : `${number(a.year_average_yield)} %`
                    : number(a.last_value, a.last_value < 1 ? 3 : 2)}
                </span>
              </Link>
              <button
                className={`favorite-button ${favorites[a.id] ? `is-favorite ${favorites[a.id]}` : ""}`}
                aria-label={favoriteLabel(favorites[a.id], a.name)}
                title={favoriteLabel(favorites[a.id], a.name)}
                aria-pressed={!!favorites[a.id]}
                onClick={() => onToggleFavorite(a.id)}
              >
                <Icon name="star" size={15} />
              </button>
            </div>
          </Fragment>
        ))}
        {loading && (
          <div className="library-empty" role="status">
            <span className="spinner" />
            Chargement…
          </div>
        )}
        {error && (
          <div className="library-empty error" role="alert">
            {error}
            <button onClick={onRetry} className="secondary-button">
              Réessayer
            </button>
          </div>
        )}
        {!loading && !error && !filtered.length && (
          <div className="library-empty">
            <Icon name={category === "stock" ? "stock" : "search"} size={28} />
            <strong>
              {query || (category === "stock" && dividendOnly)
                ? "Aucun résultat"
                : "Votre sélection commence ici"}
            </strong>
            <p>
              {category === "stock" && dividendOnly
                ? "Activez l’indicateur Dividende sur les actions de votre choix."
                : query
                  ? "Essayez un autre nom ou symbole."
                  : isLibrary(category)
                    ? category === "portfolio"
                      ? "Une étoile or indique un actif détenu."
                      : "Une étoile argent place un actif dans votre watchlist."
                    : category === "stock"
                      ? "Ajoutez les actions que vous souhaitez suivre."
                      : "Lancez le worker pour importer les historiques."}
            </p>
            {category === "stock" && !query && (
              <button className="secondary-button" onClick={onAdd}>
                <Icon name="plus" size={14} />
                Ajouter une action
              </button>
            )}
          </div>
        )}
      </nav>
    </aside>
  );
}

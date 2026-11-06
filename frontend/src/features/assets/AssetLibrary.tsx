import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { Tooltip } from "../../components/Tooltip";
import { Icon } from "../../components/Icon";
import { categories, date, number } from "../../lib/format";
import type { Asset, Category } from "../../lib/types";
export function AssetLibrary({
  assets,
  category,
  selected,
  loading,
  error,
  onAdd,
  onRetry,
}: {
  assets: Asset[];
  category: Category;
  selected?: string;
  loading: boolean;
  error: string;
  onAdd: () => void;
  onRetry: () => void;
}) {
  const [query, setQuery] = useState("");
  const list = useRef<HTMLElement>(null);
  const search = useRef<HTMLInputElement>(null);
  const selectionAvailable = assets.some((asset) => asset.id === selected);
  useEffect(() => setQuery(""), [category]);
  useEffect(() => {
    const item = list.current?.querySelector<HTMLElement>("[aria-current]");
    if (!item || !list.current) return;
    if (matchMedia("(max-width: 700px)").matches)
      list.current.scrollLeft = item.offsetLeft - list.current.offsetLeft;
    else list.current.scrollTop = item.offsetTop - list.current.offsetTop - 80;
  }, [selected, category, selectionAvailable, query]);
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
      a.category === category &&
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
  const total = assets.filter((a) => a.category === category).length;
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
        {categories.find((c) => c.id === category)?.name}
        <span>{total}</span>
      </h2>
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
        {filtered.map((a) => (
          <Link
            key={a.id}
            title={
              a.category === "bond"
                ? `${a.name} · moyenne sur ${a.year_yield_samples} observation(s) · dernière donnée ${date(a.last_date)}`
                : a.name
            }
            to={`/assets/${a.id}`}
            aria-current={selected === a.id ? "page" : undefined}
          >
            <span className={`list-symbol ${a.category}`}>
              {a.country_code ??
                (a.id.startsWith("yf-")
                  ? a.id.slice(3).split("-")[0].slice(0, 3).toUpperCase()
                  : a.name.slice(0, 2))}
            </span>
            <span className="list-name">
              <strong>{a.name}</strong>
              <small>
                {a.id.startsWith("yf-")
                  ? a.id.slice(3).toUpperCase()
                  : a.metric === "yield"
                    ? "Souverain · %"
                    : a.unit}
              </small>
            </span>
            <span className="list-value">
              {category === "bond"
                ? a.year_average_yield == null
                  ? "—"
                  : `${number(a.year_average_yield)} %`
                : number(a.last_value, a.last_value < 1 ? 3 : 2)}
            </span>
          </Link>
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
              {query ? "Aucun résultat" : "Votre sélection commence ici"}
            </strong>
            <p>
              {query
                ? "Essayez un autre nom ou symbole."
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
      <div className="library-bottom">
        <span className="status-dot" />
        Stockage local<span>SQLite</span>
      </div>
    </aside>
  );
}

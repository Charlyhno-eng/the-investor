export type Favorite = "gold" | "silver";
export type Favorites = Record<string, Favorite>;
export function readFavorites(): Favorites {
  try {
    const value: unknown = JSON.parse(
      localStorage.getItem("investor-favorites") ?? "{}",
    );
    if (Array.isArray(value))
      return Object.fromEntries(
        value.filter((id) => typeof id === "string").map((id) => [id, "gold"]),
      );
    if (value && typeof value === "object")
      return Object.fromEntries(
        Object.entries(value).filter(
          ([, status]) => status === "gold" || status === "silver",
        ),
      ) as Favorites;
  } catch {
    /* Keep the library usable when storage is unavailable. */
  }
  return {};
}
export const favoriteRank = (status?: Favorite) =>
  status === "gold" ? 2 : status === "silver" ? 1 : 0;
export const favoriteLabel = (status?: Favorite, name = "") =>
  status === "gold"
    ? `Détenu${name ? ` : ${name}` : ""} · Passer en watchlist`
    : status === "silver"
      ? `Watchlist${name ? ` : ${name}` : ""} · Retirer des favoris`
      : `Ajouter ${name ? `${name} ` : ""}aux actifs détenus`;

export type Library = "portfolio" | "watchlist";
export const isLibrary = (value: unknown): value is Library =>
  value === "portfolio" || value === "watchlist";

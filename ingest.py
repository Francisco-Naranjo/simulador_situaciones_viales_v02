from scripts.ingest import DIMENSIONES_EMBEDDING, MODELO_EMBEDDINGS, construir_indice

if __name__ == "__main__":
    res = construir_indice()
    print(f"[OK] {res['total_fragmentos']} articulos detectados ({res['huerfanos']} huerfanos)")
    print(f"[OK] Cartero en espanol: {MODELO_EMBEDDINGS} ({DIMENSIONES_EMBEDDING} dimensiones, distancia coseno)")
    print(f"[OK] chroma_db/ y data/index/ -> col.count() = {res['total_fragmentos']}")
    for f in res["fuentes"]:
        print(f"  - {f['documento']} ({f['archivo']}): {f['fragmentos']} articulos, {f['huerfanos']} huerfanos")

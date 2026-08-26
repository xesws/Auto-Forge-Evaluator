.PHONY: all clean

TECTONIC ?= tectonic
LATEXMK  ?= latexmk

all: main.pdf

main.pdf: main.tex part1.tex part2.tex part3.tex neurips_2026.sty
	@if command -v $(LATEXMK) >/dev/null 2>&1; then \
	  $(LATEXMK) -pdf -interaction=nonstopmode -halt-on-error main.tex; \
	elif command -v $(TECTONIC) >/dev/null 2>&1; then \
	  $(TECTONIC) -X compile --keep-logs main.tex; \
	else \
	  echo "need latexmk or tectonic" >&2; exit 1; \
	fi

clean:
	rm -f main.aux main.log main.out main.fls main.fdb_latexmk main.synctex.gz
	$(LATEXMK) -C main.tex >/dev/null 2>&1 || true

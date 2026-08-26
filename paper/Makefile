.PHONY: all clean supp

TECTONIC ?= tectonic
LATEXMK  ?= latexmk

# Ledger: latexmk/pdflatex are not installed on this Mac.
# Build uses tectonic 0.16.9. Both engines are acceptable.

all: main.pdf

main.pdf: main.tex part1.tex part2.tex part3.tex refs.bib neurips_2026.sty figures/architecture.tex
	@if command -v $(LATEXMK) >/dev/null 2>&1; then \
	  $(LATEXMK) -pdf -interaction=nonstopmode -halt-on-error main.tex; \
	elif command -v $(TECTONIC) >/dev/null 2>&1; then \
	  $(TECTONIC) -X compile --keep-logs --keep-intermediates main.tex; \
	else \
	  echo "need latexmk or tectonic" >&2; exit 1; \
	fi

supp.pdf: supp.tex supplementary/table61.tex neurips_2026.sty
	@if command -v $(LATEXMK) >/dev/null 2>&1; then \
	  $(LATEXMK) -pdf -interaction=nonstopmode -halt-on-error supp.tex; \
	elif command -v $(TECTONIC) >/dev/null 2>&1; then \
	  $(TECTONIC) -X compile --keep-logs --keep-intermediates supp.tex; \
	else \
	  echo "need latexmk or tectonic" >&2; exit 1; \
	fi

supp: supp.pdf

clean:
	rm -f main.aux main.log main.out main.fls main.fdb_latexmk main.synctex.gz main.bbl main.blg
	rm -f supp.aux supp.log supp.out supp.fls supp.fdb_latexmk supp.synctex.gz
	$(LATEXMK) -C main.tex >/dev/null 2>&1 || true
	$(LATEXMK) -C supp.tex >/dev/null 2>&1 || true

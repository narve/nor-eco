# Verifisering (WS6)

Independent check, 2026-10-28, by an agent that had no part in building the site. It fetched the original sources
itself (SSB API, regjeringen.no, NBIM, Statens eierrapport) and did not use `data/raw`. It edited nothing.

## Result
- About 30 displayed numbers traced to the original source: all match (rounding noted below). Bulk comparisons of the processed
  series against the API for statsbudsjett, økonomi, sysselsetting and staten showed 0 differences.
- All 54 definition quotes are verbatim at their URLs; all 28 registry URLs return 200.
- Held: no mention of media or politicians, no download functionality, licences as the publishers state them,
  claim labels used consistently.

## Found and fixed
| Finding | Fix |
|---|---|
| The staten page printed «0 ansatte» for RHF and kategori 1/2: `dataset_value` summed only exact leaf codes | `build.py` sums all leaves under a parent node and raises on a selection with no facts; regression test in `tests/test_staten.py` |
| «11,8 % av alle sysselsatte» was our own division without a marker | Labelled as utledet with the formula |
| Hard-coded claims that depend on data («nesten samme antall», «starter i 2015») | Removed |
| Statements about budget vs accounts and about statens vs offentlig forvaltnings utgifter without a source | Reworded to what the cited SSB text says |
| Evaluative wording («trykkfeil», «begge er riktige») | Neutral wording |

## Known and left as is
- Forslag 2027, inntekter utenom petroleum: the table in the source prints 1 725,1 and the text 1 725; the components sum to 1 725,0.
  The site shows 1 725,0 (source rounding, 0,1 mrd. kr).
- «Aktivitetskorreksjon og andre justeringer» (31,7 mrd. kr) is the residual between the Finansdepartementet's structural figure and our
  oljekorrigert figure. The Finansdepartementet's own activity corrections for 2025 are much smaller, so the label is hedged
  and the derivation is shown, but the residual is not itemised by any source.
- Definitions of «petroleum» differ between sources (national accounts, varehandel, statsbudsjettet); the pages state this in the pairs section.
- Some explanatory sentences state general facts without an inline citation (for example what BNP covers, current vs fixed prices,
  that petroleum tax is part of Skatter og avgifter). They are consistent with the numbers but not quoted.
- The statement that no single official source covers all publicly funded private providers is not sourced.
- Statens eierrapport is read from the HTML page, not the PDF; totals and a sample of companies matched, not all 64 rows by hand.
- Not checked by this agent: year-by-year values of `registerstatus_20_66` and older years of `registerstatus_15_74` (only 2025 and a sample).
  Chart behaviour is covered by the Playwright tests, not by this check.

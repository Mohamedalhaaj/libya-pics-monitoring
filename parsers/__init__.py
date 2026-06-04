from __future__ import annotations

from parsers.base import BaseParser
from parsers.generic import GenericListParser
from parsers.source_specific import (
    AddressLibyaParser,
    AlMenassaParser,
    AlShahedParser,
    AlSaaa24Parser,
    AlWasatParser,
    AsharqAlAwsatParser,
    EanLibyaParser,
    LanaParser,
    Libya24Parser,
    LibyaHeraldParser,
    LibyaObserverParser,
    LibyaReviewParser,
    RNAReportageParser,
)


PARSERS: dict[str, type[BaseParser]] = {
    "generic_list": GenericListParser,
    "address_libya": AddressLibyaParser,
    "al_menassa": AlMenassaParser,
    "al_shahed": AlShahedParser,
    "al_saaa_24": AlSaaa24Parser,
    "al_wasat": AlWasatParser,
    "asharq_al_awsat": AsharqAlAwsatParser,
    "ean_libya": EanLibyaParser,
    "lana": LanaParser,
    "libya_24": Libya24Parser,
    "libya_herald": LibyaHeraldParser,
    "libya_observer": LibyaObserverParser,
    "libya_review": LibyaReviewParser,
    "rna_reportage": RNAReportageParser,
}


def get_parser(parser_name: str) -> type[BaseParser]:
    try:
        return PARSERS[parser_name]
    except KeyError as exc:
        available = ", ".join(sorted(PARSERS))
        raise ValueError(f"Unknown parser '{parser_name}'. Available parsers: {available}") from exc

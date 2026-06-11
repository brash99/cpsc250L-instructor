#!/usr/bin/env python3
"""
grade_lab08.py

Automated Lab 8 checker for CPSC 250L student forks.

Lab 8: Object-Oriented Programming Review Challenge
Default folder: labs/lab08_inheritance_polymorphism  (override with --lab-path)

This grader follows the report-oriented style of the Lab 6 / Lab 7 graders:
  - reads a students.csv roster
  - clones or updates each student repo
  - finds book.py, bookstore_inventory.py, and booklist.csv
  - supplies the canonical CSV if the data file is missing
  - checks behavior in a way that is intentionally flexible about implementation style
  - focuses on the output and behavior required by the provided main program
  - writes a detailed CSV report

The grader avoids obscure edge cases.  It gives most credit for:
  - creating a list of Book objects from booklist.csv
  - printing usable Book strings
  - finding Octavia Butler books
  - sorting books alphabetically by title
  - producing the expected main-program section output

Run:

python grade_lab08.py \
  --students students.csv \
  --workdir student_repos \
  --report reports/lab08_report.csv \
  --exclude-test \
  --lab-path labs/lab08_inheritance_polymorphism
"""

from __future__ import annotations

import argparse
import ast
import csv
import importlib.util
import re
import shutil
import subprocess
import sys
import types
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


CANONICAL_CSV_TEXT = "title,author,year,genre,pages,rating\nKindred,Octavia Butler,1979,Science Fiction,264,4.8\nParable of the Sower,Octavia Butler,1993,Science Fiction,345,4.7\nParable of the Talents,Octavia Butler,1998,Science Fiction,407,4.6\nDawn,Octavia Butler,1987,Science Fiction,248,4.5\nAdulthood Rites,Octavia Butler,1988,Science Fiction,288,4.4\nImago,Octavia Butler,1989,Science Fiction,320,4.4\nWild Seed,Octavia Butler,1980,Fantasy,320,4.4\nMind of My Mind,Octavia Butler,1977,Science Fiction,240,4.2\nClay's Ark,Octavia Butler,1984,Science Fiction,256,4.1\nPatternmaster,Octavia Butler,1976,Science Fiction,280,4.0\nFoundation,Isaac Asimov,1951,Science Fiction,255,4.6\nFoundation and Empire,Isaac Asimov,1952,Science Fiction,247,4.5\nSecond Foundation,Isaac Asimov,1953,Science Fiction,240,4.5\nPrelude to Foundation,Isaac Asimov,1988,Science Fiction,403,4.3\nForward the Foundation,Isaac Asimov,1993,Science Fiction,428,4.3\nI Robot,Isaac Asimov,1950,Science Fiction,224,4.5\nThe Caves of Steel,Isaac Asimov,1953,Science Fiction,270,4.4\nThe Naked Sun,Isaac Asimov,1957,Science Fiction,288,4.3\nThe Robots of Dawn,Isaac Asimov,1983,Science Fiction,435,4.4\nRobots and Empire,Isaac Asimov,1985,Science Fiction,448,4.2\nDune,Frank Herbert,1965,Science Fiction,412,4.9\nDune Messiah,Frank Herbert,1969,Science Fiction,256,4.2\nChildren of Dune,Frank Herbert,1976,Science Fiction,444,4.5\nGod Emperor of Dune,Frank Herbert,1981,Science Fiction,454,4.3\nHeretics of Dune,Frank Herbert,1984,Science Fiction,480,4.1\nChapterhouse Dune,Frank Herbert,1985,Science Fiction,496,4.1\nThe Left Hand of Darkness,Ursula K. Le Guin,1969,Science Fiction,304,4.5\nThe Dispossessed,Ursula K. Le Guin,1974,Science Fiction,387,4.6\nA Wizard of Earthsea,Ursula K. Le Guin,1968,Fantasy,205,4.4\nThe Tombs of Atuan,Ursula K. Le Guin,1971,Fantasy,180,4.2\nThe Farthest Shore,Ursula K. Le Guin,1972,Fantasy,240,4.3\nTehanu,Ursula K. Le Guin,1990,Fantasy,288,4.1\nNeuromancer,William Gibson,1984,Cyberpunk,271,4.3\nCount Zero,William Gibson,1986,Cyberpunk,246,4.1\nMona Lisa Overdrive,William Gibson,1988,Cyberpunk,320,4.0\nPattern Recognition,William Gibson,2003,Cyberpunk,356,4.0\nSnow Crash,Neal Stephenson,1992,Cyberpunk,480,4.4\nCryptonomicon,Neal Stephenson,1999,Cyberpunk,918,4.5\nAnathem,Neal Stephenson,2008,Science Fiction,937,4.3\nSeveneves,Neal Stephenson,2015,Science Fiction,880,4.2\n1984,George Orwell,1949,Dystopian,328,4.7\nAnimal Farm,George Orwell,1945,Dystopian,112,4.6\nBrave New World,Aldous Huxley,1932,Dystopian,311,4.3\nFahrenheit 451,Ray Bradbury,1953,Dystopian,194,4.5\nThe Martian Chronicles,Ray Bradbury,1950,Science Fiction,256,4.4\nDo Androids Dream of Electric Sheep?,Philip K. Dick,1968,Science Fiction,224,4.5\nUbik,Philip K. Dick,1969,Science Fiction,216,4.4\nA Scanner Darkly,Philip K. Dick,1977,Science Fiction,251,4.3\nThe Man in the High Castle,Philip K. Dick,1962,Science Fiction,274,4.2\nFlow My Tears the Policeman Said,Philip K. Dick,1974,Science Fiction,240,4.1\nChildhood's End,Arthur C. Clarke,1953,Science Fiction,224,4.4\n2001 A Space Odyssey,Arthur C. Clarke,1968,Science Fiction,297,4.5\nRendezvous with Rama,Arthur C. Clarke,1973,Science Fiction,256,4.4\nThe Songs of Distant Earth,Arthur C. Clarke,1986,Science Fiction,320,4.1\nThe Fifth Season,N. K. Jemisin,2015,Fantasy,512,4.7\nThe Obelisk Gate,N. K. Jemisin,2016,Fantasy,448,4.6\nThe Stone Sky,N. K. Jemisin,2017,Fantasy,416,4.6\nThe Hundred Thousand Kingdoms,N. K. Jemisin,2010,Fantasy,432,4.3\nThe Broken Kingdoms,N. K. Jemisin,2010,Fantasy,416,4.2\nThe Kingdom of Gods,N. K. Jemisin,2011,Fantasy,448,4.1\nBeloved,Toni Morrison,1987,Literary Fiction,324,4.6\nSong of Solomon,Toni Morrison,1977,Literary Fiction,352,4.5\nSula,Toni Morrison,1973,Literary Fiction,192,4.3\nJazz,Toni Morrison,1992,Literary Fiction,240,4.1\nInvisible Man,Ralph Ellison,1952,Literary Fiction,581,4.6\nNative Son,Richard Wright,1940,Literary Fiction,544,4.4\nThe Color Purple,Alice Walker,1982,Literary Fiction,304,4.5\nTheir Eyes Were Watching God,Zora Neale Hurston,1937,Literary Fiction,224,4.6\nSlaughterhouse Five,Kurt Vonnegut,1969,Science Fiction,275,4.5\nCat's Cradle,Kurt Vonnegut,1963,Science Fiction,304,4.4\nBreakfast of Champions,Kurt Vonnegut,1973,Satire,320,4.1\nPlayer Piano,Kurt Vonnegut,1952,Science Fiction,352,4.0\nThe Hobbit,J. R. R. Tolkien,1937,Fantasy,310,4.8\nThe Fellowship of the Ring,J. R. R. Tolkien,1954,Fantasy,423,4.9\nThe Two Towers,J. R. R. Tolkien,1954,Fantasy,352,4.8\nThe Return of the King,J. R. R. Tolkien,1955,Fantasy,416,4.9\nThe Silmarillion,J. R. R. Tolkien,1977,Fantasy,365,4.3\nA Game of Thrones,George R. R. Martin,1996,Fantasy,694,4.7\nA Clash of Kings,George R. R. Martin,1998,Fantasy,768,4.6\nA Storm of Swords,George R. R. Martin,2000,Fantasy,973,4.8\nA Feast for Crows,George R. R. Martin,2005,Fantasy,753,4.2\nA Dance with Dragons,George R. R. Martin,2011,Fantasy,1016,4.3\nThe Name of the Wind,Patrick Rothfuss,2007,Fantasy,662,4.7\nThe Wise Man's Fear,Patrick Rothfuss,2011,Fantasy,994,4.5\nMistborn,Brandon Sanderson,2006,Fantasy,541,4.7\nThe Well of Ascension,Brandon Sanderson,2007,Fantasy,590,4.5\nThe Hero of Ages,Brandon Sanderson,2008,Fantasy,572,4.6\nThe Way of Kings,Brandon Sanderson,2010,Fantasy,1007,4.8\nWords of Radiance,Brandon Sanderson,2014,Fantasy,1087,4.9\nOathbringer,Brandon Sanderson,2017,Fantasy,1248,4.7\nElantris,Brandon Sanderson,2005,Fantasy,638,4.2\nWarbreaker,Brandon Sanderson,2009,Fantasy,688,4.4\nLeviathan Wakes,James S. A. Corey,2011,Science Fiction,561,4.6\nCaliban's War,James S. A. Corey,2012,Science Fiction,595,4.5\nAbaddon's Gate,James S. A. Corey,2013,Science Fiction,547,4.4\nCibola Burn,James S. A. Corey,2014,Science Fiction,583,4.2\nNemesis Games,James S. A. Corey,2015,Science Fiction,544,4.6\nBabylon's Ashes,James S. A. Corey,2016,Science Fiction,608,4.3\nPersepolis Rising,James S. A. Corey,2017,Science Fiction,560,4.4\nTiamat's Wrath,James S. A. Corey,2019,Science Fiction,544,4.7\nProject Hail Mary,Andy Weir,2021,Science Fiction,496,4.8\nThe Martian,Andy Weir,2011,Science Fiction,369,4.7\nArtemis,Andy Weir,2017,Science Fiction,320,4.1\nReady Player One,Ernest Cline,2011,Science Fiction,374,4.4\nReady Player Two,Ernest Cline,2020,Science Fiction,366,3.8\nThe Hunger Games,Suzanne Collins,2008,Dystopian,374,4.6\nCatching Fire,Suzanne Collins,2009,Dystopian,391,4.7\nMockingjay,Suzanne Collins,2010,Dystopian,390,4.2\nThe Handmaid's Tale,Margaret Atwood,1985,Dystopian,311,4.4\nOryx and Crake,Margaret Atwood,2003,Dystopian,376,4.1\nThe Testaments,Margaret Atwood,2019,Dystopian,432,4.3\nStation Eleven,Emily St. John Mandel,2014,Science Fiction,352,4.3\nSea of Tranquility,Emily St. John Mandel,2022,Science Fiction,272,4.2\nCloud Atlas,David Mitchell,2004,Science Fiction,544,4.3\nThe Road,Cormac McCarthy,2006,Post Apocalyptic,287,4.4\nWorld War Z,Max Brooks,2006,Horror,342,4.2\nDracula,Bram Stoker,1897,Horror,418,4.4\nFrankenstein,Mary Shelley,1818,Horror,280,4.5\nThe Shining,Stephen King,1977,Horror,447,4.6\nIt,Stephen King,1986,Horror,1138,4.5\nMisery,Stephen King,1987,Horror,320,4.4\nThe Stand,Stephen King,1978,Horror,1153,4.6\nCarrie,Stephen King,1974,Horror,199,4.0\nHarry Potter and the Sorcerer's Stone,J. K. Rowling,1997,YA Fantasy,309,4.9\nHarry Potter and the Chamber of Secrets,J. K. Rowling,1998,YA Fantasy,341,4.8\nHarry Potter and the Prisoner of Azkaban,J. K. Rowling,1999,YA Fantasy,435,4.9\nHarry Potter and the Goblet of Fire,J. K. Rowling,2000,YA Fantasy,734,4.8\nHarry Potter and the Order of the Phoenix,J. K. Rowling,2003,YA Fantasy,870,4.7\nHarry Potter and the Half Blood Prince,J. K. Rowling,2005,YA Fantasy,652,4.8\nHarry Potter and the Deathly Hallows,J. K. Rowling,2007,YA Fantasy,759,4.9\nPercy Jackson and the Lightning Thief,Rick Riordan,2005,YA Fantasy,377,4.7\nThe Sea of Monsters,Rick Riordan,2006,YA Fantasy,279,4.5\nThe Titan's Curse,Rick Riordan,2007,YA Fantasy,312,4.6\nThe Battle of the Labyrinth,Rick Riordan,2008,YA Fantasy,361,4.6\nThe Last Olympian,Rick Riordan,2009,YA Fantasy,381,4.8\nThe Lost Hero,Rick Riordan,2010,YA Fantasy,553,4.4\nThe Son of Neptune,Rick Riordan,2011,YA Fantasy,521,4.5\nThe Mark of Athena,Rick Riordan,2012,YA Fantasy,586,4.7\nThe House of Hades,Rick Riordan,2013,YA Fantasy,597,4.8\nThe Blood of Olympus,Rick Riordan,2014,YA Fantasy,516,4.3\nEragon,Christopher Paolini,2002,YA Fantasy,544,4.3\nEldest,Christopher Paolini,2005,YA Fantasy,704,4.1\nBrisingr,Christopher Paolini,2008,YA Fantasy,763,4.2\nInheritance,Christopher Paolini,2011,YA Fantasy,860,4.1\nThe Golden Compass,Philip Pullman,1995,YA Fantasy,399,4.3\nThe Subtle Knife,Philip Pullman,1997,YA Fantasy,326,4.2\nThe Amber Spyglass,Philip Pullman,2000,YA Fantasy,518,4.4\nShadow and Bone,Leigh Bardugo,2012,YA Fantasy,358,4.0\nSiege and Storm,Leigh Bardugo,2013,YA Fantasy,435,4.0\nRuin and Rising,Leigh Bardugo,2014,YA Fantasy,422,4.1\nSix of Crows,Leigh Bardugo,2015,YA Fantasy,465,4.7\nCrooked Kingdom,Leigh Bardugo,2016,YA Fantasy,536,4.6\nThrone of Glass,Sarah J. Maas,2012,YA Fantasy,404,4.2\nCrown of Midnight,Sarah J. Maas,2013,YA Fantasy,432,4.3\nHeir of Fire,Sarah J. Maas,2014,YA Fantasy,565,4.5\nQueen of Shadows,Sarah J. Maas,2015,YA Fantasy,656,4.6\nEmpire of Storms,Sarah J. Maas,2016,YA Fantasy,693,4.7\nTower of Dawn,Sarah J. Maas,2017,YA Fantasy,664,4.3\nKingdom of Ash,Sarah J. Maas,2018,YA Fantasy,980,4.8\nA Court of Thorns and Roses,Sarah J. Maas,2015,Fantasy Romance,432,4.2\nA Court of Mist and Fury,Sarah J. Maas,2016,Fantasy Romance,626,4.8\nA Court of Wings and Ruin,Sarah J. Maas,2017,Fantasy Romance,705,4.5\nThe Cruel Prince,Holly Black,2018,YA Fantasy,384,4.2\nThe Wicked King,Holly Black,2019,YA Fantasy,336,4.3\nThe Queen of Nothing,Holly Black,2019,YA Fantasy,320,4.2\nRed Queen,Victoria Aveyard,2015,YA Fantasy,383,4.0\nGlass Sword,Victoria Aveyard,2016,YA Fantasy,444,3.9\nKing's Cage,Victoria Aveyard,2017,YA Fantasy,507,4.0\nWar Storm,Victoria Aveyard,2018,YA Fantasy,662,3.8\nCinder,Marissa Meyer,2012,YA Science Fiction,387,4.3\nScarlet,Marissa Meyer,2013,YA Science Fiction,452,4.3\nCress,Marissa Meyer,2014,YA Science Fiction,560,4.5\nWinter,Marissa Meyer,2015,YA Science Fiction,832,4.4\nThe Selection,Kiera Cass,2012,YA Romance,336,4.1\nThe Elite,Kiera Cass,2013,YA Romance,336,4.0\nThe One,Kiera Cass,2014,YA Romance,323,4.2\nDivergent,Veronica Roth,2011,YA Dystopian,487,4.2\nInsurgent,Veronica Roth,2012,YA Dystopian,525,4.0\nAllegiant,Veronica Roth,2013,YA Dystopian,526,3.7\nThe Maze Runner,James Dashner,2009,YA Dystopian,375,4.1\nThe Scorch Trials,James Dashner,2010,YA Dystopian,361,4.0\nThe Death Cure,James Dashner,2011,YA Dystopian,325,3.9\nLegend,Marie Lu,2011,YA Dystopian,305,4.2\nProdigy,Marie Lu,2013,YA Dystopian,371,4.2\nChampion,Marie Lu,2013,YA Dystopian,369,4.1\nChildren of Blood and Bone,Tomi Adeyemi,2018,YA Fantasy,544,4.4\nChildren of Virtue and Vengeance,Tomi Adeyemi,2019,YA Fantasy,425,4.0\nThe Priory of the Orange Tree,Samantha Shannon,2019,Fantasy,848,4.5\nA Day of Fallen Night,Samantha Shannon,2023,Fantasy,880,4.3\nThe Eye of the World,Robert Jordan,1990,Fantasy,814,4.5\nThe Great Hunt,Robert Jordan,1990,Fantasy,705,4.4\nThe Dragon Reborn,Robert Jordan,1991,Fantasy,624,4.3\nThe Shadow Rising,Robert Jordan,1992,Fantasy,1007,4.6\nThe Fires of Heaven,Robert Jordan,1993,Fantasy,963,4.4\nLord of Chaos,Robert Jordan,1994,Fantasy,1049,4.5\nThe Blade Itself,Joe Abercrombie,2006,Fantasy,515,4.3\nBefore They Are Hanged,Joe Abercrombie,2007,Fantasy,539,4.4\nLast Argument of Kings,Joe Abercrombie,2008,Fantasy,560,4.5\nThe Lies of Locke Lamora,Scott Lynch,2006,Fantasy,499,4.6\nRed Seas Under Red Skies,Scott Lynch,2007,Fantasy,509,4.3\nThe Republic of Thieves,Scott Lynch,2013,Fantasy,676,4.1\n"

EXPECTED_NUM_BOOKS = 201
EXPECTED_OCTAVIA_TITLES = [
    "Kindred",
    "Parable of the Sower",
    "Parable of the Talents",
    "Dawn",
    "Adulthood Rites",
    "Imago",
    "Wild Seed",
    "Mind of My Mind",
    "Clay's Ark",
    "Patternmaster",
]
EXPECTED_SORTED_FIRST_TITLES = ["1984", "A Court of Mist and Fury", "A Court of Thorns and Roses"]
EXPECTED_SORTED_LAST_TITLE = "Wild Seed"
EXPECTED_MAIN_OUTPUT_CLUES = [
    "Full Inventory",
    "Total inventory:",
    "Books by Octavia Butler",
    "Low Stock Books",
    "Sorted by Title",
    "Kindred",
    "Parable of the Sower",
    "1984",
]
EXPECTED_BOOK_METHODS = ["__init__", "add_stock", "sell_copies", "__str__", "__lt__"]
EXPECTED_INVENTORY_FUNCTIONS = [
    "create_inventory",
    "print_inventory",
    "find_by_author",
    "find_low_stock",
    "print_books",
    "main",
]


# -----------------------------------------------------------------------------
# Basic command / Git helpers
# -----------------------------------------------------------------------------


def run_command(command: List[str], cwd: Optional[Path] = None, timeout: int = 20) -> Tuple[int, str, str]:
    try:
        result = subprocess.run(command, cwd=cwd, timeout=timeout, text=True, capture_output=True)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", f"Command timed out after {timeout} seconds: {' '.join(command)}"
    except Exception as exc:
        return 1, "", f"Command failed: {exc}"


def clone_or_update_repo(repo_url: str, repo_dir: Path) -> Tuple[bool, str]:
    if not repo_dir.exists():
        code, out, err = run_command(["git", "clone", repo_url, str(repo_dir)], timeout=60)
        if code != 0:
            return False, err or out
        return True, "cloned"

    if not (repo_dir / ".git").exists():
        return False, f"{repo_dir} exists but is not a git repository"

    run_command(["git", "fetch", "--all"], cwd=repo_dir, timeout=60)
    code, out, err = run_command(["git", "checkout", "main"], cwd=repo_dir)
    if code != 0:
        run_command(["git", "checkout", "master"], cwd=repo_dir)

    code, out, err = run_command(["git", "pull"], cwd=repo_dir, timeout=60)
    if code != 0:
        return False, err or out

    return True, "updated"


def is_usable_path(path: Path) -> bool:
    excluded = {".git", ".venv", "venv", "__pycache__"}
    return not any(part in excluded for part in path.parts)


def find_file(repo_dir: Path, filename: str) -> Optional[Path]:
    candidates = [p for p in repo_dir.rglob(filename) if is_usable_path(p)]
    if not candidates:
        return None
    candidates.sort(key=lambda p: ("lab08" not in str(p).lower() and "lab8" not in str(p).lower(), len(p.parts), str(p)))
    return candidates[0]


def find_lab8_file_set(repo_dir: Path, lab_path: Optional[str] = None) -> Tuple[Optional[Path], Optional[Path], Optional[Path], str]:
    """Find book.py / bookstore_inventory.py / booklist.csv as one coherent lab folder.

    Several student repos eventually contain multiple copies of starter files.
    This function strongly prefers a directory containing both Python files,
    especially under --lab-path or a path containing lab08/lab8.
    """
    book_files = [p for p in repo_dir.rglob("book.py") if is_usable_path(p)]
    inv_files = [p for p in repo_dir.rglob("bookstore_inventory.py") if is_usable_path(p)]
    csv_files = [p for p in repo_dir.rglob("booklist.csv") if is_usable_path(p)]

    by_dir: Dict[Path, Dict[str, Path]] = {}
    for p in book_files:
        by_dir.setdefault(p.parent, {})["book"] = p
    for p in inv_files:
        by_dir.setdefault(p.parent, {})["inventory"] = p
    for p in csv_files:
        by_dir.setdefault(p.parent, {})["csv"] = p

    paired_dirs = [d for d, files in by_dir.items() if "book" in files and "inventory" in files]

    def rel_str(path: Path) -> str:
        try:
            return str(path.relative_to(repo_dir))
        except ValueError:
            return str(path)

    def score_dir(path: Path) -> Tuple[int, int, str]:
        rel = rel_str(path).lower()
        supplied = lab_path.lower().rstrip("/") if lab_path else ""
        if supplied and (rel == supplied or rel.startswith(supplied + "/")):
            primary = 0
        elif "lab08" in rel or "lab8" in rel:
            primary = 1
        else:
            primary = 2
        penalty = 0
        for token in ["template", "templates", "starter", "starter_code", "old", "archive", "solution"]:
            if token in rel:
                penalty += 1
        has_csv_penalty = 0 if "csv" in by_dir.get(path, {}) else 1
        return (primary, penalty + has_csv_penalty, rel)

    if paired_dirs:
        paired_dirs.sort(key=score_dir)
        chosen = paired_dirs[0]
        files = by_dir[chosen]
        csv_path = files.get("csv") or find_file(repo_dir, "booklist.csv")
        return files.get("book"), files.get("inventory"), csv_path, f"paired files selected from {rel_str(chosen)}"

    return find_file(repo_dir, "book.py"), find_file(repo_dir, "bookstore_inventory.py"), find_file(repo_dir, "booklist.csv"), "fallback independent file search used"


def infer_lab_path_from_found_files(repo_dir: Path, *paths: Optional[Path]) -> Optional[str]:
    for path in paths:
        if path is None:
            continue
        try:
            rel = path.relative_to(repo_dir)
        except ValueError:
            continue
        parts = rel.parts
        for i, part in enumerate(parts):
            lowered = part.lower()
            if lowered.startswith("lab08") or lowered.startswith("lab8"):
                return str(Path(*parts[: i + 1]))
        if len(parts) >= 2 and parts[0] == "labs":
            return str(Path(parts[0], parts[1]))
    return None


# -----------------------------------------------------------------------------
# Python parsing / import helpers
# -----------------------------------------------------------------------------


def parse_python(py_path: Path) -> Tuple[Optional[ast.Module], str]:
    try:
        return ast.parse(py_path.read_text(encoding="utf-8")), "ok"
    except Exception as exc:
        return None, str(exc)


def get_function_names(tree: ast.Module) -> List[str]:
    return [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]


def get_class_method_names(tree: ast.Module, class_name: str) -> Tuple[bool, List[str]]:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return True, [item.name for item in node.body if isinstance(item, ast.FunctionDef)]
    return False, []


def write_canonical_csv_if_needed(lab_dir: Path) -> Path:
    csv_path = lab_dir / "booklist.csv"
    if not csv_path.exists():
        csv_path.write_text(CANONICAL_CSV_TEXT, encoding="utf-8")
    return csv_path


def import_book_module(book_path: Path) -> Tuple[Optional[Any], str]:
    try:
        module_name = f"student_book_{abs(hash(str(book_path)))}"
        spec = importlib.util.spec_from_file_location(module_name, book_path)
        if spec is None or spec.loader is None:
            return None, "Could not create import spec."
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, "ok"
    except Exception as exc:
        return None, f"Import book.py failed: {exc}"


def load_inventory_without_running_main(inventory_path: Path, book_path: Path) -> Tuple[Optional[Any], str]:
    tree, parse_note = parse_python(inventory_path)
    if tree is None:
        return None, f"Parse failed: {parse_note}"

    allowed_nodes = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef))]
    safe_tree = ast.Module(body=allowed_nodes, type_ignores=[])
    ast.fix_missing_locations(safe_tree)

    module = types.ModuleType("student_bookstore_inventory")
    module.__file__ = str(inventory_path)

    old_path = list(sys.path)
    old_book = sys.modules.get("book")
    old_cwd = Path.cwd()

    try:
        sys.path.insert(0, str(inventory_path.parent))
        book_module, book_note = import_book_module(book_path)
        if book_module is None:
            return None, book_note
        sys.modules["book"] = book_module
        code = compile(safe_tree, filename=str(inventory_path), mode="exec")
        # Some create_inventory implementations open booklist.csv relative to cwd.
        # Temporarily run in the lab directory so those also work.
        import os
        os.chdir(inventory_path.parent)
        exec(code, module.__dict__)
        return module, "ok"
    except Exception as exc:
        return None, f"Load bookstore_inventory.py failed: {exc}"
    finally:
        try:
            import os
            os.chdir(old_cwd)
        except Exception:
            pass
        sys.path = old_path
        if old_book is None:
            sys.modules.pop("book", None)
        else:
            sys.modules["book"] = old_book


def safe_call(func: Any, *args: Any, cwd: Optional[Path] = None) -> Tuple[bool, Any, str]:
    old_cwd = Path.cwd()
    try:
        if cwd is not None:
            import os
            os.chdir(cwd)
        value = func(*args)
        return True, value, "ok"
    except Exception as exc:
        return False, None, str(exc)
    finally:
        if cwd is not None:
            try:
                import os
                os.chdir(old_cwd)
            except Exception:
                pass


# -----------------------------------------------------------------------------
# Book / inventory behavior tests
# -----------------------------------------------------------------------------


def get_book_attr(book: Any, *names: str) -> Any:
    for name in names:
        if hasattr(book, name):
            return getattr(book, name)
    return None


def title_of(book: Any) -> str:
    value = get_book_attr(book, "title", "book_title")
    return "" if value is None else str(value)


def author_of(book: Any) -> str:
    value = get_book_attr(book, "author", "book_author")
    return "" if value is None else str(value)


def numeric_attr(book: Any, *names: str) -> Optional[float]:
    value = get_book_attr(book, *names)
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def construct_book(Book: Any, title="Test Book", author="Test Author", year=2024, genre="Fiction", pages=123, rating=4.5) -> Tuple[Optional[Any], str]:
    attempts = [
        (title, author, year, genre, pages, rating),
        (title, author, str(year), genre, str(pages), str(rating)),
        (title, author, year, genre, pages, rating, 0),
        (title, author, str(year), genre, str(pages), str(rating), "0"),
        (title, author),
    ]
    last_error = ""
    for args in attempts:
        try:
            return Book(*args), "ok"
        except Exception as exc:
            last_error = str(exc)
    return None, f"Could not construct Book with common signatures: {last_error}"


def test_book_class(book_module: Any) -> Dict[str, str]:
    result = {
        "book_class_behavior_correct": "no",
        "book_constructor_works": "no",
        "book_attributes_reasonable": "no",
        "book_str_readable": "no",
        "book_lt_sorts_by_title": "no",
        "book_stock_methods_work": "n/a",
        "book_notes": "",
    }

    if not hasattr(book_module, "Book"):
        result["book_notes"] += "Book class not found. "
        return result

    Book = book_module.Book
    book, note = construct_book(Book)
    if book is None:
        result["book_notes"] += note + ". "
        return result
    result["book_constructor_works"] = "yes"

    try:
        checks = [
            str(get_book_attr(book, "title", "book_title")) == "Test Book",
            str(get_book_attr(book, "author", "book_author")) == "Test Author",
            str(get_book_attr(book, "genre", "category")) == "Fiction",
        ]
        if all(checks):
            result["book_attributes_reasonable"] = "yes"
        else:
            result["book_notes"] += "Book object did not expose expected title/author/genre attributes. "
    except Exception as exc:
        result["book_notes"] += f"Could not inspect Book attributes: {exc}. "

    try:
        text = str(book)
        if all(clue in text for clue in ["Test Book", "Test Author"]) and "pass" not in text.lower():
            result["book_str_readable"] = "yes"
        else:
            result["book_notes"] += f"Book __str__ did not include useful identifying info; got {text!r}. "
    except Exception as exc:
        result["book_notes"] += f"Book __str__ raised: {exc}. "

    try:
        z_book, _ = construct_book(Book, title="Zoo Story")
        a_book, _ = construct_book(Book, title="Apple Story")
        if z_book is not None and a_book is not None:
            ordered = sorted([z_book, a_book])
            if title_of(ordered[0]) == "Apple Story" and title_of(ordered[1]) == "Zoo Story":
                result["book_lt_sorts_by_title"] = "yes"
            else:
                result["book_notes"] += "Book __lt__ did not sort alphabetically by title. "
    except Exception as exc:
        result["book_notes"] += f"Book sorting raised: {exc}. "

    # Stock methods are part of the template, but the supplied CSV has no stock
    # column. Award this as a small optional/bonus-like check only when a student
    # has a recognizable stock attribute.
    try:
        stock_names = ["quantity", "stock", "copies", "num_copies", "inventory"]
        initial = None
        stock_attr = None
        for name in stock_names:
            if hasattr(book, name):
                stock_attr = name
                initial = getattr(book, name)
                break
        if stock_attr is None:
            result["book_stock_methods_work"] = "n/a"
        else:
            book.add_stock(5)
            after_add = getattr(book, stock_attr)
            sale_result = book.sell_copies(2)
            after_sale = getattr(book, stock_attr)
            if after_add == initial + 5 and after_sale == initial + 3 and sale_result is True:
                result["book_stock_methods_work"] = "yes"
            else:
                result["book_stock_methods_work"] = "no"
                result["book_notes"] += "Stock methods did not add/sell copies as expected. "
    except Exception as exc:
        result["book_stock_methods_work"] = "no"
        result["book_notes"] += f"Stock method check raised: {exc}. "

    core_keys = ["book_constructor_works", "book_attributes_reasonable", "book_str_readable", "book_lt_sorts_by_title"]
    if all(result[key] == "yes" for key in core_keys):
        result["book_class_behavior_correct"] = "yes"
    return result


def test_inventory_functions(inv_module: Any, lab_dir: Path) -> Dict[str, str]:
    result = {
        "create_inventory_returns_list": "no",
        "create_inventory_count_correct": "no",
        "create_inventory_book_objects": "no",
        "create_inventory_first_record_correct": "no",
        "total_inventory_correct": "no",
        "find_by_author_correct": "no",
        "find_low_stock_callable": "no",
        "sorted_inventory_correct": "no",
        "inventory_functions_behavior_correct": "no",
        "inventory_notes": "",
    }

    if not hasattr(inv_module, "create_inventory"):
        result["inventory_notes"] += "create_inventory not found. "
        return result

    ok, books, note = safe_call(inv_module.create_inventory, cwd=lab_dir)
    if not ok:
        result["inventory_notes"] += f"create_inventory raised: {note}. "
        return result

    if isinstance(books, list):
        result["create_inventory_returns_list"] = "yes"
    else:
        result["inventory_notes"] += f"create_inventory returned {type(books).__name__}, not list. "
        return result

    if len(books) == EXPECTED_NUM_BOOKS:
        result["create_inventory_count_correct"] = "yes"
    else:
        result["inventory_notes"] += f"Expected {EXPECTED_NUM_BOOKS} books, got {len(books)}. "

    if books and all(hasattr(book, "__class__") and book.__class__.__name__ == "Book" for book in books[:5]):
        result["create_inventory_book_objects"] = "yes"
    else:
        result["inventory_notes"] += "First few inventory items are not Book objects. "

    try:
        first = books[0]
        if title_of(first) == "Kindred" and author_of(first) == "Octavia Butler":
            result["create_inventory_first_record_correct"] = "yes"
        else:
            result["inventory_notes"] += f"First book expected Kindred by Octavia Butler, got {title_of(first)!r} by {author_of(first)!r}. "
    except Exception as exc:
        result["inventory_notes"] += f"Could not inspect first record: {exc}. "

    # Accept either total_inventory or total_inventory_value, since the starter
    # comments use one name but the supplied main program calls the other.
    total_func = getattr(inv_module, "total_inventory_value", None) or getattr(inv_module, "total_inventory", None)
    if total_func is None:
        result["inventory_notes"] += "Neither total_inventory_value nor total_inventory found. "
    else:
        ok, total, note = safe_call(total_func, books, cwd=lab_dir)
        if ok:
            # The CSV has one row per book but no stock/quantity column.
            # In the supplied completed solution, each Book starts with amount = 0,
            # so the main-program-aligned total inventory is 0.
            try:
                total_as_int = int(total)
            except Exception:
                total_as_int = None
            if total == 0 or total_as_int == 0:
                result["total_inventory_correct"] = "yes"
            else:
                result["inventory_notes"] += f"Total inventory expected 0, got {total!r}. "
        else:
            result["inventory_notes"] += f"Total inventory function raised: {note}. "

    if hasattr(inv_module, "find_by_author"):
        ok, octavia_books, note = safe_call(inv_module.find_by_author, books, "Octavia Butler", cwd=lab_dir)
        if ok and isinstance(octavia_books, list):
            titles = [title_of(book) for book in octavia_books]
            if titles == EXPECTED_OCTAVIA_TITLES:
                result["find_by_author_correct"] = "yes"
            elif set(titles) == set(EXPECTED_OCTAVIA_TITLES) and len(titles) == len(EXPECTED_OCTAVIA_TITLES):
                # Order is not the conceptual point here.
                result["find_by_author_correct"] = "yes"
                result["inventory_notes"] += "Octavia Butler books found, but returned in a different order. "
            else:
                result["inventory_notes"] += f"find_by_author returned titles {titles[:12]!r}. "
        else:
            result["inventory_notes"] += f"find_by_author failed: {note}. "
    else:
        result["inventory_notes"] += "find_by_author not found. "

    if hasattr(inv_module, "find_low_stock"):
        ok, low_stock, note = safe_call(inv_module.find_low_stock, books, 3, cwd=lab_dir)
        if ok and isinstance(low_stock, list):
            # Do not require exact content because the CSV has no stock column
            # and reasonable implementations vary. Just require a list and no crash.
            result["find_low_stock_callable"] = "yes"
        else:
            result["inventory_notes"] += f"find_low_stock failed: {note}. "
    else:
        result["inventory_notes"] += "find_low_stock not found. "

    try:
        sorted_books = sorted(books)
        sorted_titles = [title_of(book) for book in sorted_books]
        expected_titles = sorted([title_of(book) for book in books], key=lambda t: str(t).lower())
        if sorted_titles == expected_titles:
            result["sorted_inventory_correct"] = "yes"
        else:
            result["inventory_notes"] += f"Sorted titles begin {sorted_titles[:5]!r} and end {sorted_titles[-3:]!r}. "
    except Exception as exc:
        result["inventory_notes"] += f"Sorting inventory raised: {exc}. "

    keys = [
        "create_inventory_returns_list",
        "create_inventory_count_correct",
        "create_inventory_book_objects",
        "create_inventory_first_record_correct",
        "total_inventory_correct",
        "find_by_author_correct",
        "find_low_stock_callable",
        "sorted_inventory_correct",
    ]
    if all(result[key] == "yes" for key in keys):
        result["inventory_functions_behavior_correct"] = "yes"
    return result


# -----------------------------------------------------------------------------
# Terminal output tests
# -----------------------------------------------------------------------------


def run_main_from_terminal(inventory_path: Path) -> Tuple[bool, str]:
    code, out, err = run_command([sys.executable, str(inventory_path.name)], cwd=inventory_path.parent, timeout=15)
    if code == 0:
        return True, out
    return False, err or out


def output_has_expected_content(output: str) -> Tuple[bool, str]:
    notes = []
    for clue in EXPECTED_MAIN_OUTPUT_CLUES:
        if clue not in output:
            notes.append(f"Missing expected output clue: {clue}")

    lowered = output.lower()
    if "dummy string" in lowered:
        notes.append("Output appears to contain placeholder text: dummy string")
    if "not implemented" in lowered:
        notes.append("Output appears to contain placeholder text: not implemented")
    # Only flag pass when it appears as a standalone placeholder line/word.
    # Do not flag real titles like The Golden Compass.
    if re.search(r"(?m)^\s*pass\s*$", output, flags=re.IGNORECASE):
        notes.append("Output appears to contain placeholder text: pass")

    # Check that the sorted section appears to be alphabetized without requiring
    # exact formatting of every line.
    if "Sorted by Title" in output and "1984" not in output.split("Sorted by Title", 1)[-1][:500]:
        notes.append("Sorted section does not appear to begin with 1984")

    return len(notes) == 0, "; ".join(notes)


# -----------------------------------------------------------------------------
# Git metadata helpers
# -----------------------------------------------------------------------------


def count_commits_touching_path(repo_dir: Path, lab_path: Optional[str]) -> Tuple[Optional[int], str]:
    if not lab_path:
        return None, "lab path not provided"
    code, out, err = run_command(["git", "rev-list", "--count", "HEAD", "--", lab_path], cwd=repo_dir)
    if code != 0:
        return None, err or out
    try:
        return int(out), "ok"
    except ValueError:
        return None, f"could not parse commit count: {out}"


def get_recent_lab_commits(repo_dir: Path, lab_path: Optional[str], n: int = 8) -> str:
    if not lab_path:
        return ""
    code, out, err = run_command(["git", "log", "--oneline", f"-{n}", "--", lab_path], cwd=repo_dir)
    return out if code == 0 else err


def get_recent_commits(repo_dir: Path, n: int = 10) -> str:
    code, out, err = run_command(["git", "log", "--oneline", f"-{n}"], cwd=repo_dir)
    return out if code == 0 else err


def get_branch_info(repo_dir: Path) -> str:
    code, out, err = run_command(["git", "branch", "-a"], cwd=repo_dir)
    return out if code == 0 else err


def is_working_tree_clean(repo_dir: Path) -> Tuple[bool, str]:
    code, out, err = run_command(["git", "status", "--porcelain"], cwd=repo_dir)
    if code != 0:
        return False, err or out
    if out.strip() == "":
        return True, "clean"
    return False, out.replace("\n", " | ")


# -----------------------------------------------------------------------------
# Student grading
# -----------------------------------------------------------------------------


def grade_student(row: Dict[str, str], workdir: Path, lab_path: Optional[str]) -> Dict[str, str]:
    name = row["name"].strip()
    username = row["github_username"].strip()
    repo_url = row["repo_url"].strip()
    repo_dir = workdir / username

    result: Dict[str, str] = {
        "name": name,
        "github_username": username,
        "repo_url": repo_url,
        "type": row.get("type", "student").strip() or "student",
        "clone_or_update": "no",
        "book_exists": "no",
        "book_path": "",
        "bookstore_inventory_exists": "no",
        "bookstore_inventory_path": "",
        "booklist_csv_exists": "no",
        "booklist_csv_path": "",
        "book_class_exists": "no",
        "book_methods_present": "no",
        "missing_book_methods": "",
        "inventory_functions_present": "no",
        "missing_inventory_functions": "",
        "book_constructor_works": "no",
        "book_attributes_reasonable": "no",
        "book_str_readable": "no",
        "book_lt_sorts_by_title": "no",
        "book_stock_methods_work": "n/a",
        "create_inventory_returns_list": "no",
        "create_inventory_count_correct": "no",
        "create_inventory_book_objects": "no",
        "create_inventory_first_record_correct": "no",
        "total_inventory_correct": "no",
        "find_by_author_correct": "no",
        "find_low_stock_callable": "no",
        "sorted_inventory_correct": "no",
        "main_runs_from_terminal": "no",
        "main_output_readable": "no",
        "main_output": "",
        "lab_path_checked": "",
        "commits_touching_lab": "",
        "meaningful_lab_commit_evidence": "no",
        "recent_lab_commits": "",
        "working_tree_clean": "no",
        "recent_commits": "",
        "branch_info": "",
        "auto_score_out_of_20": "0",
        "manual_review_out_of_0": "",
        "total_score_out_of_20": "",
        "notes": "",
    }

    ok, message = clone_or_update_repo(repo_url, repo_dir)
    result["clone_or_update"] = "yes" if ok else "no"
    if not ok:
        result["notes"] = message
        return result

    book_path, inventory_path, csv_path, file_selection_note = find_lab8_file_set(repo_dir, lab_path)
    effective_lab_path = infer_lab_path_from_found_files(repo_dir, book_path, inventory_path, csv_path) or lab_path
    result["lab_path_checked"] = effective_lab_path or ""
    result["notes"] += file_selection_note + ". "
    if lab_path and effective_lab_path and lab_path != effective_lab_path:
        result["notes"] += f"Using inferred lab path {effective_lab_path} for Git evidence instead of supplied --lab-path {lab_path}. "

    if book_path is not None:
        result["book_exists"] = "yes"
        result["book_path"] = str(book_path.relative_to(repo_dir))
    if inventory_path is not None:
        result["bookstore_inventory_exists"] = "yes"
        result["bookstore_inventory_path"] = str(inventory_path.relative_to(repo_dir))
    if csv_path is not None:
        result["booklist_csv_exists"] = "yes"
        result["booklist_csv_path"] = str(csv_path.relative_to(repo_dir))

    if book_path is None or inventory_path is None:
        result["notes"] += "Missing book.py or bookstore_inventory.py. "
    else:
        lab_dir = inventory_path.parent
        if csv_path is None or csv_path.parent != lab_dir:
            write_canonical_csv_if_needed(lab_dir)
            result["notes"] += "Canonical booklist.csv supplied for grading. "
        elif csv_path.name != "booklist.csv":
            shutil.copy(csv_path, lab_dir / "booklist.csv")

        book_tree, book_parse_note = parse_python(book_path)
        inv_tree, inv_parse_note = parse_python(inventory_path)

        if book_tree is None:
            result["notes"] += f"book.py parse failed: {book_parse_note}. "
        else:
            class_exists, methods = get_class_method_names(book_tree, "Book")
            result["book_class_exists"] = "yes" if class_exists else "no"
            missing_methods = [m for m in EXPECTED_BOOK_METHODS if m not in methods]
            result["missing_book_methods"] = ";".join(missing_methods)
            result["book_methods_present"] = "yes" if not missing_methods else "no"

        if inv_tree is None:
            result["notes"] += f"bookstore_inventory.py parse failed: {inv_parse_note}. "
        else:
            function_names = get_function_names(inv_tree)
            expected = list(EXPECTED_INVENTORY_FUNCTIONS)
            # Accept either spelling for the total function.
            if "total_inventory" not in function_names and "total_inventory_value" not in function_names:
                expected.append("total_inventory or total_inventory_value")
            missing_functions = [f for f in expected if f not in function_names and f != "total_inventory or total_inventory_value"]
            result["missing_inventory_functions"] = ";".join(missing_functions)
            has_total = "total_inventory" in function_names or "total_inventory_value" in function_names
            result["inventory_functions_present"] = "yes" if (not missing_functions and has_total) else "no"

        book_module, book_note = import_book_module(book_path)
        if book_module is None:
            result["notes"] += book_note + ". "
        else:
            book_results = test_book_class(book_module)
            for key in ["book_constructor_works", "book_attributes_reasonable", "book_str_readable", "book_lt_sorts_by_title", "book_stock_methods_work"]:
                result[key] = book_results[key]
            result["notes"] += book_results.get("book_notes", "")

        inv_module, inv_note = load_inventory_without_running_main(inventory_path, book_path)
        if inv_module is None:
            result["notes"] += inv_note + ". "
        else:
            inventory_results = test_inventory_functions(inv_module, lab_dir)
            for key in [
                "create_inventory_returns_list",
                "create_inventory_count_correct",
                "create_inventory_book_objects",
                "create_inventory_first_record_correct",
                "total_inventory_correct",
                "find_by_author_correct",
                "find_low_stock_callable",
                "sorted_inventory_correct",
            ]:
                result[key] = inventory_results[key]
            result["notes"] += inventory_results.get("inventory_notes", "")

        main_ok, main_output = run_main_from_terminal(inventory_path)
        result["main_runs_from_terminal"] = "yes" if main_ok else "no"
        result["main_output"] = main_output[:4000]
        if main_ok:
            readable, output_note = output_has_expected_content(main_output)
            result["main_output_readable"] = "yes" if readable else "no"
            if output_note:
                result["notes"] += output_note + ". "
        else:
            result["notes"] += f"Main program did not run: {main_output[:500]}. "

    # Git evidence
    commits, commit_note = count_commits_touching_path(repo_dir, effective_lab_path)
    if commits is not None:
        result["commits_touching_lab"] = str(commits)
        if commits >= 1:
            result["meaningful_lab_commit_evidence"] = "yes"
    else:
        result["notes"] += f"Could not count commits touching lab path: {commit_note}. "

    result["recent_lab_commits"] = get_recent_lab_commits(repo_dir, effective_lab_path)
    result["recent_commits"] = get_recent_commits(repo_dir)
    result["branch_info"] = get_branch_info(repo_dir)
    clean, status_note = is_working_tree_clean(repo_dir)
    result["working_tree_clean"] = "yes" if clean else "no"
    if not clean:
        result["notes"] += f"Working tree not clean: {status_note}. "

    score = 0
    score_items = [
        ("book_exists", 1),
        ("bookstore_inventory_exists", 1),
        ("book_class_exists", 1),
        ("book_methods_present", 1),
        ("inventory_functions_present", 1),
        ("book_constructor_works", 1),
        ("book_attributes_reasonable", 1),
        ("book_str_readable", 1),
        ("book_lt_sorts_by_title", 2),
        ("create_inventory_returns_list", 1),
        ("create_inventory_count_correct", 2),
        ("create_inventory_book_objects", 1),
        ("create_inventory_first_record_correct", 1),
        ("total_inventory_correct", 1),
        ("find_by_author_correct", 2),
        ("find_low_stock_callable", 1),
        ("sorted_inventory_correct", 2),
        ("main_runs_from_terminal", 1),
        ("main_output_readable", 1),
    ]
    # Scale to 20 because the raw item total is 23. This lets the grader be
    # forgiving when one small structural expectation differs but the program works.
    raw_possible = sum(points for _, points in score_items)
    raw_score = sum(points for key, points in score_items if result.get(key) == "yes")
    score = round(20 * raw_score / raw_possible)

    # Do not penalize the stock methods if the CSV-based lab never uses stock.
    result["auto_score_out_of_20"] = str(score)
    result["total_score_out_of_20"] = str(score)
    return result


# -----------------------------------------------------------------------------
# CLI / report writer
# -----------------------------------------------------------------------------


def read_students(students_csv: Path, exclude_test: bool = False) -> List[Dict[str, str]]:
    with students_csv.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    required = {"name", "github_username", "repo_url"}
    missing = required - set(rows[0].keys() if rows else [])
    if missing:
        raise ValueError(f"students.csv missing required columns: {sorted(missing)}")
    if exclude_test:
        rows = [row for row in rows if row.get("type", "student").strip().lower() != "test"]
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Grade CPSC 250L Lab 8 student repositories.")
    parser.add_argument("--students", required=True, type=Path, help="CSV with columns name,github_username,repo_url[,type]")
    parser.add_argument("--workdir", required=True, type=Path, help="Directory where repositories are cloned/updated")
    parser.add_argument("--report", required=True, type=Path, help="Output CSV report path")
    parser.add_argument("--lab-path", default="labs/lab08_inheritance_polymorphism", help="Expected lab path inside each repo")
    parser.add_argument("--exclude-test", action="store_true", help="Exclude rows where type == test")
    args = parser.parse_args()

    args.workdir.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)

    rows = read_students(args.students, exclude_test=args.exclude_test)
    results: List[Dict[str, str]] = []

    for row in rows:
        print(f"Grading {row.get('github_username', '').strip()} ...", flush=True)
        results.append(grade_student(row, args.workdir, args.lab_path))

    if not results:
        print("No students to grade.")
        return

    fieldnames = list(results[0].keys())
    with args.report.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"Wrote report to {args.report}")


if __name__ == "__main__":
    main()

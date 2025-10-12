import { useMemo } from "react";

import "./Chessboard.css";

interface ChessboardProps {
  fen?: string;
  highlights?: string[];
  showCoordinates?: boolean;
  showPieces?: boolean;
}

const files = ["a", "b", "c", "d", "e", "f", "g", "h"] as const;

const pieceGlyph: Record<string, string> = {
  p: "♟",
  r: "♜",
  n: "♞",
  b: "♝",
  q: "♛",
  k: "♚",
  P: "♙",
  R: "♖",
  N: "♘",
  B: "♗",
  Q: "♕",
  K: "♔",
};

function squareId(file: string, rank: number) {
  return `${file}${rank}`;
}

function parseFen(fen?: string): (string | null)[][] {
  if (!fen) {
    return Array.from({ length: 8 }, () => Array(8).fill(null));
  }

  const placement = fen.split(" ")[0];
  const ranks = placement?.split("/");
  if (!ranks || ranks.length !== 8) {
    return Array.from({ length: 8 }, () => Array(8).fill(null));
  }

  return ranks.map((rank) => {
    const squares: (string | null)[] = [];
    for (const char of rank) {
      if (/^[1-8]$/.test(char)) {
        squares.push(...Array(Number(char)).fill(null));
      } else {
        squares.push(char);
      }
    }
    while (squares.length < 8) {
      squares.push(null);
    }
    return squares.slice(0, 8);
  });
}

export function Chessboard({ fen, highlights = [], showCoordinates = true, showPieces = true }: ChessboardProps) {
  const layout = useMemo(() => parseFen(fen), [fen]);

  return (
    <div className="board">
      {Array.from({ length: 8 }, (_, rowIdx) => 8 - rowIdx).map((rank) => (
        <div className="row" key={rank}>
          {files.map((file, fileIdx) => {
            const id = squareId(file, rank);
            const isLight = (fileIdx + rank) % 2 === 0;
            const isHighlighted = highlights.includes(id);
            const rowIndex = 8 - rank;
            const pieceCode = showPieces ? layout[rowIndex]?.[fileIdx] ?? null : null;
            const glyph = pieceCode ? pieceGlyph[pieceCode] ?? pieceCode : null;

            return (
              <div
                key={id}
                className={`square ${isLight ? "light" : "dark"} ${isHighlighted ? "highlight" : ""}`.trim()}
              >
                {glyph && <span className="piece">{glyph}</span>}
                {showCoordinates && <span className="coord">{id}</span>}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

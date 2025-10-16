import { useMemo, memo } from "react";

import "./Chessboard.css";

interface ChessboardProps {
  fen?: string;
  highlights?: string[];
  showCoordinates?: boolean;
  showPieces?: boolean;
}

const files = ["a", "b", "c", "d", "e", "f", "g", "h"] as const;

const pieceImages: Record<string, string> = {
  p: "https://lichess1.org/assets/_W5EUck/piece/cburnett/bP.svg",
  r: "https://lichess1.org/assets/_W5EUck/piece/cburnett/bR.svg",
  n: "https://lichess1.org/assets/_W5EUck/piece/cburnett/bN.svg",
  b: "https://lichess1.org/assets/_W5EUck/piece/cburnett/bB.svg",
  q: "https://lichess1.org/assets/_W5EUck/piece/cburnett/bQ.svg",
  k: "https://lichess1.org/assets/_W5EUck/piece/cburnett/bK.svg",
  P: "https://lichess1.org/assets/_W5EUck/piece/cburnett/wP.svg",
  R: "https://lichess1.org/assets/_W5EUck/piece/cburnett/wR.svg",
  N: "https://lichess1.org/assets/_W5EUck/piece/cburnett/wN.svg",
  B: "https://lichess1.org/assets/_W5EUck/piece/cburnett/wB.svg",
  Q: "https://lichess1.org/assets/_W5EUck/piece/cburnett/wQ.svg",
  K: "https://lichess1.org/assets/_W5EUck/piece/cburnett/wK.svg",
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

export const Chessboard = memo(function Chessboard({ fen, highlights = [], showCoordinates = true, showPieces = true }: ChessboardProps) {
  // Only parse FEN when pieces need to be shown - prevents flash when toggled off
  const layout = useMemo(() => showPieces ? parseFen(fen) : null, [fen, showPieces]);

  return (
    <div className="board">
      {Array.from({ length: 8 }, (_, rowIdx) => 8 - rowIdx).map((rank) => (
        <div className="row" key={rank}>
          {files.map((file, fileIdx) => {
            const id = squareId(file, rank);
            const isLight = (fileIdx + rank) % 2 === 0;
            const isHighlighted = highlights.includes(id);
            const rowIndex = 8 - rank;
            const pieceCode = layout ? layout[rowIndex]?.[fileIdx] ?? null : null;
            const pieceImage = pieceCode ? pieceImages[pieceCode] : null;

            return (
              <div
                key={id}
                className={`square ${isLight ? "light" : "dark"} ${isHighlighted ? "highlight" : ""}`.trim()}
              >
                {showPieces && pieceImage && (
                  <img 
                    src={pieceImage} 
                    alt={pieceCode || ''} 
                    className="piece"
                    draggable={false}
                  />
                )}
                {showCoordinates && <span className="coord">{id}</span>}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
});

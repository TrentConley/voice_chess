import { useMemo, memo, useState, useEffect } from "react";

import "./Chessboard.css";
import { ChessPiece } from "./ChessPieces";

interface ChessboardProps {
  fen?: string;
  highlights?: string[];
  showCoordinates?: boolean;
  showPieces?: boolean;
}

const files = ["a", "b", "c", "d", "e", "f", "g", "h"] as const;

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
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth <= 768);
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

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

            return (
              <div
                key={id}
                className={`square ${isLight ? "light" : "dark"} ${isHighlighted ? "highlight" : ""}`.trim()}
              >
                {showPieces && pieceCode && (
                  <div className="piece">
                    <ChessPiece piece={pieceCode} mobile={isMobile} />
                  </div>
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

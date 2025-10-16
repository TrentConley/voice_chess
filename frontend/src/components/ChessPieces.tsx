interface PieceProps {
  color: 'white' | 'black';
  size?: number;
}

export function Pawn({ color, size = 40 }: PieceProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 45 45" fill="none">
      <circle cx="22.5" cy="9" r="4" fill={color === 'white' ? '#fff' : '#000'} stroke="#000" strokeWidth="1.5" />
      <path
        d="M22.5 15c-3 0-5.5 1.5-5.5 4v3c0 1 .5 1.5 1.5 1.5h8c1 0 1.5-.5 1.5-1.5v-3c0-2.5-2.5-4-5.5-4z"
        fill={color === 'white' ? '#fff' : '#000'}
        stroke="#000"
        strokeWidth="1.5"
      />
      <path
        d="M15 23.5v4.5c0 2 2.5 3.5 7.5 3.5s7.5-1.5 7.5-3.5v-4.5"
        fill={color === 'white' ? '#fff' : '#000'}
        stroke="#000"
        strokeWidth="1.5"
      />
      <path d="M13 32h19v4H13z" fill={color === 'white' ? '#fff' : '#000'} stroke="#000" strokeWidth="1.5" />
    </svg>
  );
}

export function Rook({ color, size = 40 }: PieceProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 45 45" fill="none">
      <path
        d="M9 39h27v-3H9v3zm3-3v-9h21v9M11 15v11h23V15M14 15h5v-5h-5v5zm7 0h5v-5h-5v5zm7 0h5v-5h-5v5z"
        fill={color === 'white' ? '#fff' : '#000'}
        stroke="#000"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function Knight({ color, size = 40 }: PieceProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 45 45" fill="none">
      <path
        d="M22 10c-3 0-6 2-7 5 0 0-1 3-1 6v3c0 1.5 1 2.5 2.5 2.5h11c1.5 0 2.5-1 2.5-2.5v-3c0-3-1-6-1-6-1-3-4-5-7-5z"
        fill={color === 'white' ? '#fff' : '#000'}
        stroke="#000"
        strokeWidth="1.5"
      />
      <path d="M11 39h23v-3H11v3zm2-3v-7h19v7" fill={color === 'white' ? '#fff' : '#000'} stroke="#000" strokeWidth="1.5" />
      <circle cx="20" cy="18" r="1.5" fill={color === 'white' ? '#000' : '#fff'} />
    </svg>
  );
}

export function Bishop({ color, size = 40 }: PieceProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 45 45" fill="none">
      <circle cx="22.5" cy="8" r="2.5" fill={color === 'white' ? '#fff' : '#000'} stroke="#000" strokeWidth="1.5" />
      <path
        d="M17 16c0-3 2.5-5.5 5.5-5.5s5.5 2.5 5.5 5.5c0 1.5-.5 2.5-1.5 3.5l-1 1v6.5c0 1-1 1.5-2.5 1.5s-2.5-.5-2.5-1.5V20.5l-1-1c-1-1-1.5-2-1.5-3.5z"
        fill={color === 'white' ? '#fff' : '#000'}
        stroke="#000"
        strokeWidth="1.5"
      />
      <path d="M13 30h19v-2H13v2z" fill={color === 'white' ? '#fff' : '#000'} stroke="#000" strokeWidth="1.5" />
      <path d="M11 39h23v-3H11v3zm2-3v-6h19v6" fill={color === 'white' ? '#fff' : '#000'} stroke="#000" strokeWidth="1.5" />
    </svg>
  );
}

export function Queen({ color, size = 40 }: PieceProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 45 45" fill="none">
      <circle cx="10" cy="12" r="2" fill={color === 'white' ? '#fff' : '#000'} stroke="#000" strokeWidth="1.5" />
      <circle cx="17" cy="8" r="2" fill={color === 'white' ? '#fff' : '#000'} stroke="#000" strokeWidth="1.5" />
      <circle cx="22.5" cy="6" r="2" fill={color === 'white' ? '#fff' : '#000'} stroke="#000" strokeWidth="1.5" />
      <circle cx="28" cy="8" r="2" fill={color === 'white' ? '#fff' : '#000'} stroke="#000" strokeWidth="1.5" />
      <circle cx="35" cy="12" r="2" fill={color === 'white' ? '#fff' : '#000'} stroke="#000" strokeWidth="1.5" />
      <path
        d="M10 14l2 10 3-8 3 8 2-8 3 8 3-8 2 10c0 2-2 3-12.5 3S8 16 8 14"
        fill={color === 'white' ? '#fff' : '#000'}
        stroke="#000"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path d="M11 39h23v-3H11v3zm2-3v-7h19v7" fill={color === 'white' ? '#fff' : '#000'} stroke="#000" strokeWidth="1.5" />
    </svg>
  );
}

export function King({ color, size = 40 }: PieceProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 45 45" fill="none">
      <path
        d="M22.5 4v4m-2.5-2h5"
        stroke="#000"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <path
        d="M22.5 8c-3.5 0-6.5 2.5-6.5 6v2c0 1.5 1 2.5 2.5 2.5h8c1.5 0 2.5-1 2.5-2.5v-2c0-3.5-3-6-6.5-6z"
        fill={color === 'white' ? '#fff' : '#000'}
        stroke="#000"
        strokeWidth="1.5"
      />
      <path
        d="M15 18.5v8c0 2 2.5 3.5 7.5 3.5s7.5-1.5 7.5-3.5v-8"
        fill={color === 'white' ? '#fff' : '#000'}
        stroke="#000"
        strokeWidth="1.5"
      />
      <path d="M11 39h23v-3H11v3zm2-3v-6h19v6" fill={color === 'white' ? '#fff' : '#000'} stroke="#000" strokeWidth="1.5" />
    </svg>
  );
}

export function ChessPiece({ piece, size = 40 }: { piece: string; size?: number }) {
  const isWhite = piece === piece.toUpperCase();
  const color = isWhite ? 'white' : 'black';
  const pieceType = piece.toLowerCase();

  switch (pieceType) {
    case 'p':
      return <Pawn color={color} size={size} />;
    case 'r':
      return <Rook color={color} size={size} />;
    case 'n':
      return <Knight color={color} size={size} />;
    case 'b':
      return <Bishop color={color} size={size} />;
    case 'q':
      return <Queen color={color} size={size} />;
    case 'k':
      return <King color={color} size={size} />;
    default:
      return null;
  }
}

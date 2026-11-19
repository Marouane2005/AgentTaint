export function Skeleton({ label = "Loading", rows = 3 }: { label?: string; rows?: number }) {
  return (
    <div className="skeleton" role="status" aria-label={label}>
      {Array.from({ length: rows }, (_, index) => (
        <span key={index} className={index === 0 ? "sk wide" : "sk"} />
      ))}
    </div>
  );
}

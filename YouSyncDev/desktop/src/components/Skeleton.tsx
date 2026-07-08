type SkeletonProps = {
  className?: string;
};

function Skeleton({ className = "" }: SkeletonProps) {
  return <span className={`skeleton ${className}`} aria-hidden="true" />;
}

function PlaylistRowsSkeleton() {
  return (
    <>
      {Array.from({ length: 6 }).map((_, index) => (
        <div className="playlist-row skeleton-row" key={index}>
          <Skeleton className="skeleton-thumb" />
          <div className="playlist-info">
            <Skeleton className="skeleton-line skeleton-wide" />
            <Skeleton className="skeleton-line skeleton-medium" />
          </div>
          <Skeleton className="skeleton-pill" />
          <Skeleton className="skeleton-line skeleton-short" />
          <Skeleton className="skeleton-line skeleton-medium" />
          <Skeleton className="skeleton-line skeleton-short" />
          <Skeleton className="skeleton-actions" />
        </div>
      ))}
    </>
  );
}

export { PlaylistRowsSkeleton, Skeleton };

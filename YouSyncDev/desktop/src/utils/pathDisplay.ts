const DEFAULT_MAX_PATH_LENGTH = "/Users/omay/Documents/all_yousync/apple".length;

export function formatPathForDisplay(path: string, maxLength = DEFAULT_MAX_PATH_LENGTH) {
  const value = path.trim();

  if (value.length <= maxLength) {
    return value;
  }

  const tail = value.slice(-(maxLength - 3));
  const separatorIndex = tail.search(/[\\/]/);

  if (separatorIndex > 0) {
    return "..." + tail.slice(separatorIndex);
  }

  return "..." + tail;
}

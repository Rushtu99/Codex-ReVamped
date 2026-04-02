export type AccountIdentityLike = {
  accountId: string;
  email: string;
  displayName: string;
};

type AccountNicknameLike = Pick<AccountIdentityLike, "accountId" | "email" | "displayName">;

function normalizeNickname(value: string): string {
  return value
    .trim()
    .replace(/[._-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function identityKey(account: AccountIdentityLike): string {
  const email = account.email.trim().toLowerCase();
  if (email) {
    return `email:${email}`;
  }
  const displayName = account.displayName.trim().toLowerCase();
  if (displayName) {
    return `display:${displayName}`;
  }
  return `id:${account.accountId}`;
}

export function buildDuplicateAccountIdSet<T extends AccountIdentityLike>(accounts: T[]): Set<string> {
  const counts = new Map<string, number>();
  for (const account of accounts) {
    const key = identityKey(account);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }

  const duplicateAccountIds = new Set<string>();
  for (const account of accounts) {
    if ((counts.get(identityKey(account)) ?? 0) > 1) {
      duplicateAccountIds.add(account.accountId);
    }
  }
  return duplicateAccountIds;
}

export function formatCompactAccountId(accountId: string, headChars = 8, tailChars = 6): string {
  const head = Math.max(1, headChars);
  const tail = Math.max(1, tailChars);
  if (accountId.length <= head + tail + 3) {
    return accountId;
  }
  return `${accountId.slice(0, head)}...${accountId.slice(-tail)}`;
}

export function formatAccountNickname(account: AccountNicknameLike): string {
  const displayName = account.displayName.trim();
  if (displayName && displayName !== account.email.trim()) {
    return normalizeNickname(displayName) || displayName;
  }

  const email = account.email.trim();
  if (email) {
    const localPart = email.split("@", 1)[0] ?? email;
    const nickname = normalizeNickname(localPart);
    if (nickname) {
      return nickname;
    }
    return email;
  }

  return formatCompactAccountId(account.accountId, 6, 4);
}

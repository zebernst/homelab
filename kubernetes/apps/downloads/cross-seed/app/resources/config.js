// Torrent content layout: Original
// Default Torrent Management Mode: Automatic
// Default Save Path: /media/downloads/torrents/seeding
// Incomplete Save Path: /media/downloads/torrents/incomplete

module.exports = {
  apiKey: process.env.CROSS_SEED_API_KEY,
  port: Number(process.env.CROSS_SEED_PORT),

  // Cross-seed
  action: "inject",
  delay: 30,
  includeNonVideos: false,
  matchMode: "partial",
  outputDir: "/config/torrents",
  seasonFromEpisodes: 0.98,
  useClientTorrents: true,

  // Qbittorrent
  qbittorrentUrl: "http://qbittorrent.downloads.svc.cluster.local",
  duplicateCategories: false,
  skipRecheck: false,

  // Linking
  linkCategory: "cross-seed",
  linkDirs: ["/media/downloads/qbittorrent/seeding/cross-seed"],
  linkType: "hardlink",

  // Connections
  radarr: [
    `http://radarr.downloads.svc.cluster.local/?apikey=${process.env.RADARR_API_KEY}`,
    `http://radarr-uhd.downloads.svc.cluster.local/?apikey=${process.env.RADARR_API_KEY}`,
  ],
  sonarr: [
    `http://sonarr.downloads.svc.cluster.local/?apikey=${process.env.SONARR_API_KEY}`,
    `http://sonarr-uhd.downloads.svc.cluster.local/?apikey=${process.env.SONARR_API_KEY}`,
  ],
  torznab: [
    2,  // PTP
    12, // TL
    18, // MLK
    19, // JPTV
    52, // SP
    53, // HUNO
    54, // HDS
    56, // GT
    57, // OE
    58, // OT
    59, // LST
  ].map(i => `http://prowlarr.downloads.svc.cluster.local/${i}/api?apikey=${process.env.PROWLARR_API_KEY}`),
};

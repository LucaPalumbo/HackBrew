// Initialize once, including when upgrading an existing standalone data volume.
try {
  db.adminCommand({ replSetGetStatus: 1 });
} catch (error) {
  if (error.code !== 94) throw error; // NotYetInitialized
  db.adminCommand({
    replSetInitiate: {
      _id: 'hackbrew',
      members: [{ _id: 0, host: 'mongo:27017' }],
    },
  });
}
quit(db.adminCommand({ hello: 1 }).isWritablePrimary ? 0 : 1);

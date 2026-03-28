pub mod admin;
pub mod calendar;
pub mod forex;
pub mod general;
pub mod market;
pub mod moderation;
pub mod ping;
pub mod stock;
pub mod sys;
pub mod twitter;
pub mod volatility;

use crate::repository::DbPool;
use poise::serenity_prelude::UserId;
use std::collections::HashSet;

#[derive(Clone)]
pub struct Data {
    pub owners: HashSet<UserId>,
    pub db: DbPool,
}

impl std::fmt::Debug for Data {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Data")
            .field("owners", &self.owners)
            .field("db", &"Arc<PgPool>")
            .finish()
    }
}

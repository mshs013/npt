<?php

/**
 * @author Sazzad Hossain <sazzad@ocmsbd.com>
 * @copyright 2017
 */

class assignedUser extends Model {

    protected $dbTable = "assignusers";
    protected $dbFields = Array (
        'user_id' => Array ('int', 'required'),
        'assignuser_id' => Array ('int', 'required')
    );
    protected $relations = Array (
        'user_id' => Array ("hasOne", "user"),
        'assignuser_id' => Array ("hasOne", "user"),
        'user' => Array ("hasOne", "user", "user_id"),
        'assignuser' => Array ("hasOne", "user", "assignuser_id")
    );
}
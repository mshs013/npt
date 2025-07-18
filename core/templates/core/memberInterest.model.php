<?php

/**
 * @author Sazzad Hossain <sazzad@ocmsbd.com>
 * @copyright 2024
 */

class member extends Model {

    protected $dbTable = "members";
    protected $primaryKey = "id";
    protected $dbFields = Array (
        'member_type' => Array ('int', 'required'),
        'member_no' => Array ('text', 'required'),
        'member_date' => Array ('date', 'required'),
        'full_name' => Array ('text', 'required'),
        'father_husband_name' => Array ('text'),
        'mother_name' => Array ('text'),
        'member_email' => Array ('text'),
        'member_photo' => Array ('text'),
        'member_sign' => Array ('text'),
        'created_by' => Array ('int'),
        'created_at' => Array ('datetime'),
        'updated_by' => Array ('int'),
        'updated_at' => Array ('datetime'),
        'deleted_at' => Array ('datetime')
    );
    protected $timestamps = Array ('created_at', 'updated_at', 'deleted_at');
    protected $users = Array ('created_by', 'updated_by');
    protected $relations = Array (
        'created_by' => Array ("hasOne", "user"),
        'updated_by' => Array ("hasOne", "user"),
        'memberType' => Array ("hasOne", "memberType", 'member_type'),
    );

}